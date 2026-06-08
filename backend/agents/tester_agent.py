"""
agents/tester_agent.py — Agent 4: Tester
=========================================
Model   : meta-llama/llama-3.3-70b-instruct:free  (primary)
Fallback: microsoft/phi-4-reasoning:free

Job:
    Coder ka code leke pytest test files generate karna,
    Docker sandbox mein run karna, aur results report karna.

How it works:
    1. Pehli baar: LLM se pytest tests generate karo
       Retry loop mein: pehle wale tests reuse karo (debugger code fix karta hai, tests nahi)
    2. Test files ko sandbox_folder mein likho
    3. Docker container mein pytest run karo (resource-limited, network-isolated)
    4. Results parse karke test_results + error_trace state mein save karo

Reads  : state["code_files"], state["task_plan"], state["sandbox_folder"],
         state["prd_text"], state["test_code"]
Writes : state["test_code"], state["test_results"], state["error_trace"],
         state["total_tokens"]

Note: Currently supports Python projects only (pytest).
      Docker must be installed and running on the host.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Any

from config import AgentName, build_messages, call_llm, settings
from graph.state import AutoDevState, RunStatus, log

logger = logging.getLogger("agentic-platform")


# ─────────────────────────────────────────────────────────────────────────────
# 1. System Prompt
# ─────────────────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """You are an expert QA engineer. You write thorough pytest test suites.

STRICT RULES:
1. Output ONLY the raw test file content — no markdown fences, no explanations.
2. Use pytest (not unittest). Import pytest at the top.
3. Add 'import sys; sys.path.insert(0, ".")' at the very top so project imports work.
4. Write REAL assertions that test actual behavior, not just "assert True".
5. Test both happy-path and edge-cases/error-cases.
6. If the code uses external services (DB, API, HTTP), mock them with unittest.mock.
7. Use descriptive test function names: test_<what>_<scenario>.
8. Keep tests focused — one assertion concept per test function.
9. Import from the project using the exact module paths from the source files.
""".strip()


# Files that don't need test generation
_SKIP_NAMES = {
    "__init__.py", "requirements.txt", "Dockerfile", "docker-compose.yml",
    "docker-compose.yaml", ".gitignore", ".env", ".env.example",
    "README.md", "Makefile", "Procfile", "package.json", "package-lock.json",
}


def _is_testable(file_path: str) -> bool:
    """Returns True if the file contains logic worth testing."""
    return Path(file_path).name not in _SKIP_NAMES


def _build_test_prompt(
    code_files: dict[str, str],
    task_plan: dict[str, Any],
) -> str:
    """Build user prompt for generating pytest tests."""
    testable = {p: c for p, c in code_files.items() if _is_testable(p)}

    snippets = []
    for path, content in testable.items():
        lines = content.splitlines()
        trimmed = "\n".join(lines[:150])
        if len(lines) > 150:
            trimmed += f"\n# ... ({len(lines) - 150} more lines)"
        snippets.append(f"── {path} ──\n{trimmed}")

    files_context = "\n\n".join(snippets) or "No testable source files."

    project_name = task_plan.get("project_name", "project")
    description = task_plan.get("project_description", "")

    return f"""## Project: {project_name}
{description}

## Source Files to Test
{files_context}

Write a COMPREHENSIVE pytest test file (tests/test_main.py) that covers
the key functions and classes in these source files.
- Test core business logic, not boilerplate/config.
- Mock external dependencies (DB, HTTP calls, filesystem).
- Include at least 2-3 tests per important function.
- Output ONLY raw Python code — no markdown fences.
""".strip()


# ─────────────────────────────────────────────────────────────────────────────
# 2. Code extraction — strip markdown fences if LLM adds them
# ─────────────────────────────────────────────────────────────────────────────

def _extract_code(raw: str) -> str:
    """Strip markdown code fences if present."""
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if len(lines) >= 3 and lines[-1].strip() == "```":
            cleaned = "\n".join(lines[1:-1])
        elif len(lines) >= 2:
            cleaned = "\n".join(lines[1:])
    return cleaned


# ─────────────────────────────────────────────────────────────────────────────
# 3. Write tests to sandbox
# ─────────────────────────────────────────────────────────────────────────────

def _write_tests_to_sandbox(sandbox_folder: str, test_code: dict[str, str]) -> None:
    """Write test files into the sandbox directory."""
    for test_path, content in test_code.items():
        full_path = Path(sandbox_folder) / test_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")


# ─────────────────────────────────────────────────────────────────────────────
# 4. Docker sandbox execution
# ─────────────────────────────────────────────────────────────────────────────

def _run_tests_in_docker(sandbox_folder: str) -> dict[str, Any]:
    """
    Run pytest inside a Docker container with resource limits.

    Returns dict matching state["test_results"] shape:
        {passed, summary, failures, stdout, stderr, exit_code}
    """
    # pip install silenced; only pytest stdout/stderr captured
    inner_cmd = (
        "pip install --quiet pytest > /dev/null 2>&1 && "
        "if [ -f requirements.txt ]; then "
        "pip install --quiet -r requirements.txt > /dev/null 2>&1; fi && "
        "python -m pytest tests/ -v --tb=short"
    )

    docker_cmd = [
        "docker", "run", "--rm",
        f"--memory={settings.sandbox_memory_mb}m",
        f"--cpu-quota={settings.sandbox_cpu_quota}",
        "-e", "PYTHONPATH=/app",
        "-v", f"{sandbox_folder}:/app",
        "-w", "/app",
        "python:3.11-slim",
        "sh", "-c", inner_cmd,
    ]

    # sandbox_timeout_s is for test execution; +120s buffer for Docker setup + pip
    total_timeout = settings.sandbox_timeout_s + 120

    try:
        result = subprocess.run(
            docker_cmd,
            capture_output=True,
            text=True,
            timeout=total_timeout,
        )
        stdout = result.stdout
        stderr = result.stderr
        exit_code = result.returncode

    except subprocess.TimeoutExpired:
        return {
            "passed": False,
            "summary": f"Timed out after {total_timeout}s",
            "failures": [{"test": "TIMEOUT", "error": f"Exceeded {total_timeout}s"}],
            "stdout": "",
            "stderr": "TimeoutExpired",
            "exit_code": -1,
        }
    except FileNotFoundError:
        return {
            "passed": False,
            "summary": "Docker not found — install Docker to run sandboxed tests",
            "failures": [{"test": "DOCKER", "error": "docker command not in PATH"}],
            "stdout": "",
            "stderr": "Docker not found",
            "exit_code": -1,
        }

    passed = exit_code == 0
    summary = _parse_summary(stdout) or ("All tests passed" if passed else "Tests failed")
    failures = _parse_failures(stdout) if not passed else []

    return {
        "passed": passed,
        "summary": summary,
        "failures": failures,
        "stdout": stdout[-3000:],   # trim to avoid bloating state
        "stderr": stderr[-1000:],
        "exit_code": exit_code,
    }


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
            error_msg = parts[1].strip() if len(parts) > 1 else "See stdout for details"
            failures.append({"test": test_name, "error": error_msg})

    if not failures:
        # Couldn't parse specific failures — capture raw output tail
        failures.append({"test": "unknown", "error": output[-500:]})

    return failures


# ─────────────────────────────────────────────────────────────────────────────
# 5. Main agent entry point
# ─────────────────────────────────────────────────────────────────────────────

async def run(state: AutoDevState) -> AutoDevState:
    """
    Orchestrator is function ko call karta hai:
        from agents.tester_agent import run as tester_run
        state = await tester_run(state)

    Steps:
        1. Retry loop hai? → existing test_code reuse karo (tests spec define karte hain,
           debugger code fix karta hai — tests same rehte hain)
           First run? → LLM se pytest tests generate karo
        2. Tests ko current sandbox_folder mein likho
        3. Docker container mein pytest run karo
        4. test_results + error_trace save karo
    """
    log(state, "Tester", "Agent started")
    run_id = state["run_id"]

    code_files: dict = state.get("code_files") or {}
    sandbox_folder: str = state.get("sandbox_folder") or ""
    task_plan: dict = state.get("task_plan") or {}
    total_tokens: int = state.get("total_tokens", 0)

    # ── Guards ────────────────────────────────────────────────────────────────
    if not code_files:
        log(state, "Tester", "ERROR: code_files empty — nothing to test")
        state["status"] = RunStatus.FAILED
        return state

    if not sandbox_folder:
        log(state, "Tester", "ERROR: sandbox_folder missing — coder did not run?")
        state["status"] = RunStatus.FAILED
        return state

    # ── Step 1: Generate or reuse tests ───────────────────────────────────────
    test_code: dict[str, str] = state.get("test_code") or {}

    if test_code:
        # Retry loop — debugger fixed code, reuse same tests
        log(state, "Tester", f"Reusing {len(test_code)} test file(s) from previous run")
    else:
        # First run — generate tests via LLM
        log(state, "Tester", "Generating pytest tests via LLM")

        user_prompt = _build_test_prompt(code_files, task_plan)
        messages = build_messages(_SYSTEM_PROMPT, user_prompt)

        try:
            llm_result = call_llm(
                agent=AgentName.TESTER,
                messages=messages,
                temperature=0.2,
                max_tokens=4096,
                run_id=run_id,
            )
        except RuntimeError as e:
            log(state, "Tester", f"LLM call failed: {e}")
            state["status"] = RunStatus.FAILED
            state["total_tokens"] = total_tokens
            return state

        raw = str(llm_result["content"])
        clean = _extract_code(raw)
        test_code = {"tests/test_main.py": clean}

        tokens_used = int(llm_result.get("total_tokens", 0))
        total_tokens += tokens_used
        log(state, "Tester", f"Tests generated ({len(clean)} chars, {tokens_used} tokens)")

    # ── Step 2: Write tests to sandbox ────────────────────────────────────────
    _write_tests_to_sandbox(sandbox_folder, test_code)
    log(state, "Tester", f"Tests written to sandbox: {sandbox_folder}")

    # ── Step 3: Run pytest in Docker sandbox ──────────────────────────────────
    log(state, "Tester", "Running pytest in Docker sandbox...")
    test_results = _run_tests_in_docker(sandbox_folder)

    log(
        state, "Tester",
        f"Result: passed={test_results['passed']} | {test_results['summary']}",
    )

    # ── Step 4: Save to state ─────────────────────────────────────────────────
    state["test_code"] = test_code
    state["test_results"] = test_results
    state["total_tokens"] = total_tokens

    if not test_results["passed"]:
        # Combine stdout + stderr for debugger to analyze
        state["error_trace"] = (
            f"Summary: {test_results['summary']}\n\n"
            f"stdout:\n{test_results['stdout']}\n\n"
            f"stderr:\n{test_results['stderr']}"
        )
        log(state, "Tester", "Tests FAILED — error_trace set for debugger")
    else:
        state["error_trace"] = None
        log(state, "Tester", "All tests PASSED ✓")

    return state
