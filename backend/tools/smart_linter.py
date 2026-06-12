"""
tools/smart_linter.py — Ruff + ESLint Wrapper (Docker Sandbox)
===============================================================
Reviewer agent isko use karta hai code quality check karne ke liye.
Python files ke liye Ruff, JS/TS files ke liye ESLint chalata hai —
dono Docker sandbox mein.

Usage:
    from tools.smart_linter import run_lint

    issues = run_lint("/path/to/sandbox_folder")
    # issues = [
    #     {"file": "app.py", "line": 12, "message": "F401: unused import"},
    #     {"file": "index.js", "line": 5, "message": "no-unused-vars: ..."},
    # ]

Docker must be installed and running on the host machine.
"""

from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path
from typing import Any

from config import settings

logger = logging.getLogger("agentic-platform")

# Cap per-linter issues to prevent state bloat
_MAX_ISSUES = 50


# ─────────────────────────────────────────────────────────────────────────────
# 1. Public API
# ─────────────────────────────────────────────────────────────────────────────

def run_lint(sandbox_folder: str) -> list[dict[str, Any]]:
    """
    Sandbox folder ko lint karta hai — auto-detect language.

    Python files milein → Ruff chalega.
    JS/TS files milein → ESLint chalega.
    Dono milein → dono chalenge, results merge.

    Parameters
    ----------
    sandbox_folder : str
        Host path to the project directory (mounted at /app inside container).

    Returns
    -------
    List of lint issues: [{"file": str, "line": int, "message": str}]
    """
    sandbox_path = Path(sandbox_folder).resolve()
    if not sandbox_path.is_dir():
        logger.warning("Lint skipped — folder not found: %s", sandbox_folder)
        return []

    has_python, has_js = _detect_languages(sandbox_path)

    issues: list[dict[str, Any]] = []

    if has_python:
        issues.extend(_run_ruff(sandbox_folder))

    if has_js:
        issues.extend(_run_eslint(sandbox_folder))

    if not has_python and not has_js:
        logger.info("No Python or JS/TS files found — lint skipped")

    return issues


# ─────────────────────────────────────────────────────────────────────────────
# 2. Language detection
# ─────────────────────────────────────────────────────────────────────────────

_PYTHON_EXTS = {".py"}
_JS_EXTS = {".js", ".jsx", ".ts", ".tsx"}
_SKIP_DIRS = {"node_modules", ".venv", "venv", "__pycache__", ".git"}


def _detect_languages(sandbox_path: Path) -> tuple[bool, bool]:
    """Scan top-level + one level deep to detect Python and JS/TS files."""
    has_python = False
    has_js = False

    for child in sandbox_path.rglob("*"):
        # Skip deep directories and known junk
        if any(part in _SKIP_DIRS for part in child.parts):
            continue
        if child.is_file():
            ext = child.suffix.lower()
            if ext in _PYTHON_EXTS:
                has_python = True
            elif ext in _JS_EXTS:
                has_js = True
        if has_python and has_js:
            break  # no need to scan further

    return has_python, has_js


# ─────────────────────────────────────────────────────────────────────────────
# 3. Ruff — Python linter
# ─────────────────────────────────────────────────────────────────────────────

def _run_ruff(sandbox_folder: str) -> list[dict[str, Any]]:
    """Run Ruff inside Docker. Returns parsed lint issues."""
    inner_cmd = (
        "pip install --quiet ruff > /dev/null 2>&1 && "
        "ruff check /app --output-format=json 2>/dev/null || true"
    )

    stdout = _docker_run(sandbox_folder, "python:3.11-slim", inner_cmd)
    if not stdout:
        return []

    try:
        raw_issues = json.loads(stdout)
    except json.JSONDecodeError:
        logger.warning("Could not parse Ruff JSON output")
        return []

    issues = []
    for item in raw_issues[:_MAX_ISSUES]:
        file_path = item.get("filename", "")
        # Strip Docker mount prefix /app/
        if file_path.startswith("/app/"):
            file_path = file_path[5:]

        code = item.get("code", "???")
        message = item.get("message", "")
        line = item.get("location", {}).get("row", 0)

        issues.append({
            "file": file_path,
            "line": line,
            "message": f"{code}: {message}",
        })

    logger.info("Ruff: %d issue(s) found", len(issues))
    return issues


# ─────────────────────────────────────────────────────────────────────────────
# 4. ESLint — JavaScript/TypeScript linter
# ─────────────────────────────────────────────────────────────────────────────

def _run_eslint(sandbox_folder: str) -> list[dict[str, Any]]:
    """Run ESLint inside Docker. Returns parsed lint issues."""
    # Use flat config auto-init so no .eslintrc needed in the project
    inner_cmd = (
        "npm install --save-dev eslint @eslint/js --silent 2>/dev/null && "
        "npx eslint /app --format=json "
        "--no-eslintrc "
        "--ext .js,.jsx,.ts,.tsx "
        "2>/dev/null || true"
    )

    stdout = _docker_run(sandbox_folder, "node:20-slim", inner_cmd)
    if not stdout:
        return []

    try:
        raw_results = json.loads(stdout)
    except json.JSONDecodeError:
        logger.warning("Could not parse ESLint JSON output")
        return []

    issues = []
    for file_result in raw_results:
        file_path = file_result.get("filePath", "")
        # Strip Docker mount prefix /app/
        if file_path.startswith("/app/"):
            file_path = file_path[5:]

        for msg in file_result.get("messages", []):
            if len(issues) >= _MAX_ISSUES:
                break
            rule = msg.get("ruleId") or "parse-error"
            text = msg.get("message", "")
            line = msg.get("line", 0)

            issues.append({
                "file": file_path,
                "line": line,
                "message": f"{rule}: {text}",
            })

        if len(issues) >= _MAX_ISSUES:
            break

    logger.info("ESLint: %d issue(s) found", len(issues))
    return issues


# ─────────────────────────────────────────────────────────────────────────────
# 5. Docker runner (shared helper)
# ─────────────────────────────────────────────────────────────────────────────

def _docker_run(sandbox_folder: str, image: str, inner_cmd: str) -> str:
    """
    Run a command inside a Docker container and return stdout.
    Returns empty string on any failure.
    """
    docker_cmd = [
        "docker", "run", "--rm",
        f"--memory={settings.sandbox_memory_mb}m",
        f"--cpu-quota={settings.sandbox_cpu_quota}",
        # "--network=none",
        "-v", f"{Path(sandbox_folder).resolve()}:/app",
        "-w", "/app",
        image,
        "sh", "-c", inner_cmd,
    ]

    try:
        result = subprocess.run(
            docker_cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )
        return result.stdout.strip()

    except subprocess.TimeoutExpired:
        logger.warning("Lint timed out | image=%s", image)
        return ""

    except FileNotFoundError:
        logger.error("Docker binary not found in PATH")
        return ""

    except OSError as e:
        logger.error("Docker lint OSError: %s", e)
        return ""
