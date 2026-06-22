"""
tools/docker_runner.py — Sandbox Code Execution via Docker
===========================================================
Tester agent isko use karta hai pytest run karne ke liye ek
resource-limited, network-isolated Docker container mein.

Usage:
    from tools.docker_runner import run_code_in_sandbox

    result = run_code_in_sandbox("/path/to/sandbox_folder")
    # result = {
    #     "passed":    bool,
    #     "summary":   str,
    #     "failures":  [{"test": str, "error": str}],
    #     "stdout":    str,
    #     "stderr":    str,
    #     "exit_code": int,
    # }

Docker must be installed and running on the host machine.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

from config import settings

logger = logging.getLogger("agentic-platform")


# ─────────────────────────────────────────────────────────────────────────────
# 1. Public API
# ─────────────────────────────────────────────────────────────────────────────

async def run_code_in_sandbox(
    sandbox_folder: str,
    *,
    test_command: str = "python -m pytest tests/ -v --tb=short",
    image: str = "python:3.11-slim",
) -> dict[str, Any]:
    """
    Docker container mein code execute karta hai.

    Parameters
    ----------
    sandbox_folder : str
        Host path to the project directory (mounted at /app inside container).
    test_command : str
        The command to run after dependencies are installed.
    image : str
        Docker image to use.

    Returns
    -------
    dict matching state["test_results"] shape:
        {passed, summary, failures, stdout, stderr, exit_code}
    """
    sandbox_path = Path(sandbox_folder).resolve()
    if not sandbox_path.is_dir():
        return _error_result(
            "SANDBOX", f"Sandbox folder not found: {sandbox_folder}"
        )

    # pip install silenced; only test stdout/stderr captured
    inner_cmd = (
        "pip install --quiet pytest > /dev/null 2>&1 && "
        "if [ -f requirements.txt ]; then "
        "pip install --quiet -r requirements.txt > /dev/null 2>&1; fi && "
        f"{test_command}"
    )

    docker_args = [
        "docker", "run", "--rm",
        # ── Resource limits ──
        f"--memory={settings.sandbox_memory_mb}m",
        f"--cpu-quota={settings.sandbox_cpu_quota}",
        # ── Network isolation ──
        # "--network=none",
        # ── Environment ──
        "-e", "PYTHONPATH=/app",
        "-e", "PYTHONDONTWRITEBYTECODE=1",
        # ── Mount project read-write ──
        "-v", f"{sandbox_path}:/app",
        "-w", "/app",
        # ── Image ──
        image,
        "sh", "-c", inner_cmd,
    ]

    # sandbox_timeout_s covers test execution; +120s buffer for Docker pull + pip
    total_timeout = settings.sandbox_timeout_s + 120

    logger.info(
        "Docker run | folder=%s timeout=%ss image=%s",
        sandbox_folder, total_timeout, image,
    )

    try:
        proc = await asyncio.create_subprocess_exec(
            *docker_args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            proc.communicate(), timeout=total_timeout
        )
        stdout = stdout_bytes.decode() if stdout_bytes else ""
        stderr = stderr_bytes.decode() if stderr_bytes else ""
        exit_code = proc.returncode or 0

    except asyncio.TimeoutError:
        logger.warning("Docker run timed out after %ss", total_timeout)
        proc.kill()
        return _error_result(
            "TIMEOUT", f"Execution timed out after {total_timeout}s"
        )

    except FileNotFoundError:
        logger.error("Docker binary not found in PATH")
        return _error_result(
            "DOCKER", "Docker not found — install Docker to run sandboxed tests"
        )

    except OSError as e:
        logger.error("Docker run OSError: %s", e)
        return _error_result("OS_ERROR", str(e))

    passed = exit_code == 0
    summary = _parse_summary(stdout) or (
        "All tests passed" if passed else "Tests failed"
    )
    failures = _parse_failures(stdout) if not passed else []

    logger.info(
        "Docker done | passed=%s exit=%s summary=%s",
        passed, exit_code, summary,
    )

    return {
        "passed": passed,
        "summary": summary,
        "failures": failures,
        "stdout": stdout[-3000:],   # trim to avoid bloating state
        "stderr": stderr[-1000:],
        "exit_code": exit_code,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 2. Pytest output parsers
# ─────────────────────────────────────────────────────────────────────────────

def _parse_summary(output: str) -> str:
    """Extract pytest summary line (e.g. '3 passed, 1 failed in 0.45s')."""
    for line in reversed(output.splitlines()):
        if "passed" in line or "failed" in line or "error" in line:
            cleaned = line.strip("= ").strip()
            if cleaned:
                return cleaned
    return ""


def _parse_failures(output: str) -> list[dict[str, str]]:
    """Extract individual failure details from pytest -v --tb=short output."""
    failures = []
    for line in output.splitlines():
        if line.startswith("FAILED "):
            parts = line.split(" - ", 1)
            test_name = parts[0].replace("FAILED", "").strip()
            error_msg = (
                parts[1].strip() if len(parts) > 1 else "See stdout for details"
            )
            failures.append({"test": test_name, "error": error_msg})

    if not failures:
        # Couldn't parse specific failures — capture raw output tail
        failures.append({"test": "unknown", "error": output[-500:]})

    return failures


# ─────────────────────────────────────────────────────────────────────────────
# 3. Helper
# ─────────────────────────────────────────────────────────────────────────────

def _error_result(error_type: str, message: str) -> dict[str, Any]:
    """Build a standardised failure result dict."""
    return {
        "passed": False,
        "summary": message,
        "failures": [{"test": error_type, "error": message}],
        "stdout": "",
        "stderr": message,
        "exit_code": -1,
    }
