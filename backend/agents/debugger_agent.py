"""
agents/debugger_agent.py — Agent 5: Debugger
=============================================
Model   : nvidia/llama-3.3-nemotron-super-49b-v1:free  (primary)
Fallback: microsoft/phi-4-reasoning:free

Job:
    Tester ke error_trace ko read karke, buggy file identify karna,
    sirf uss ek file ka targeted fix karna (full rewrite nahi),
    aur retry_count increment karna.

How it works:
    1. error_trace se Python traceback parse karke buggy file path nikalo
    2. Agar file identify ho gayi → sirf uss file + error info LLM ko bhejo
       Agar identify nahi hui → saari files bhejo, LLM se identify + fix karwao
    3. LLM se fixed file content lo (drop-in replacement)
    4. code_files mein sirf uss ek file update karo (baaki sab untouched)
    5. retry_count += 1

After this agent:
    orchestrator sends state to coder (skips LLM, just writes to new sandbox)
    → tester (re-runs same tests on fixed code)

Reads  : state["error_trace"], state["code_files"], state["test_code"],
         state["test_results"], state["retry_count"]
Writes : state["code_files"], state["retry_count"], state["total_tokens"]
"""

from __future__ import annotations

import logging
import re

from config import AgentName, build_messages, call_llm
from graph.state import AutoDevState, log

logger = logging.getLogger("agentic-platform")


# ─────────────────────────────────────────────────────────────────────────────
# 1. System Prompt
# ─────────────────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """You are an expert debugger. You fix bugs with minimal, targeted changes.

STRICT RULES:
1. Output ONLY the complete fixed file content — no markdown fences, no explanations.
2. Fix ONLY the bug causing the test failure. Do NOT refactor or restructure.
3. Keep all existing logic, comments, and structure intact.
4. If the bug is a missing import, add it. If wrong logic, fix that specific part.
5. The output must be a complete drop-in replacement for the broken file.
6. Do NOT wrap output in ```python ... ``` or any other code block.
""".strip()


# ─────────────────────────────────────────────────────────────────────────────
# 2. Identify the buggy file from error trace
# ─────────────────────────────────────────────────────────────────────────────

def _identify_buggy_file(
    error_trace: str,
    code_files: dict[str, str],
) -> str | None:
    """
    Parse error_trace to find which project file caused the failure.
    Returns the file_path key from code_files, or None.

    Strategy: Extract file paths from Python tracebacks, check innermost
    frames first (most likely location of the actual bug).
    """
    # Match: File "/app/path/to/file.py", line N
    # Docker sandbox mounts project to /app
    matches = re.findall(r'File "/?(?:app/)?(.+?\.py)", line \d+', error_trace)

    # Check innermost frames first (end of traceback = deepest call)
    for match in reversed(matches):
        clean = match.lstrip("/")
        if clean in code_files:
            return clean
        # Strip common prefixes from Docker paths
        for prefix in ("app/", "src/", "./"):
            if clean.startswith(prefix):
                stripped = clean[len(prefix):]
                if stripped in code_files:
                    return stripped

    # Fallback: check if any code_files path appears literally in error_trace
    for file_path in code_files:
        if file_path in error_trace:
            return file_path

    return None


# ─────────────────────────────────────────────────────────────────────────────
# 3. Prompt builders
# ─────────────────────────────────────────────────────────────────────────────

def _build_targeted_prompt(
    buggy_file_path: str,
    buggy_code: str,
    error_trace: str,
    test_code: dict[str, str],
    failures: list[dict[str, str]],
) -> str:
    """Prompt for fixing ONE known buggy file."""
    # Structured failure info
    failure_lines = ""
    if failures:
        failure_lines = "\n".join(
            f"  - {f['test']}: {f['error']}" for f in failures[:5]
        )

    # Test file context (trimmed)
    test_context = ""
    for path, content in test_code.items():
        lines = content.splitlines()
        trimmed = "\n".join(lines[:100])
        if len(lines) > 100:
            trimmed += f"\n# ... ({len(lines) - 100} more lines)"
        test_context += f"\n── {path} ──\n{trimmed}"

    return f"""## Test Failures
{failure_lines or "See error trace below"}

## Error Trace (from pytest)
{error_trace[:3000]}

## Test Code
{test_context or "Not available"}

## Buggy File: {buggy_file_path}
{buggy_code}

Fix the bug in "{buggy_file_path}" that is causing the test failure above.
- Make the MINIMUM change needed.
- Do NOT change function signatures, class names, or file structure.
- Output the COMPLETE fixed file — it must be a drop-in replacement.
- Output ONLY raw code — no markdown fences.
""".strip()


def _build_unidentified_prompt(
    code_files: dict[str, str],
    error_trace: str,
    test_code: dict[str, str],
    failures: list[dict[str, str]],
) -> str:
    """Fallback prompt when buggy file can't be identified from trace."""
    # All source files (trimmed)
    file_snippets = []
    for path, content in code_files.items():
        lines = content.splitlines()
        trimmed = "\n".join(lines[:120])
        if len(lines) > 120:
            trimmed += f"\n# ... ({len(lines) - 120} more lines)"
        file_snippets.append(f"── {path} ──\n{trimmed}")
    files_context = "\n\n".join(file_snippets)

    # Failure info
    failure_lines = ""
    if failures:
        failure_lines = "\n".join(
            f"  - {f['test']}: {f['error']}" for f in failures[:5]
        )

    # Test context
    test_context = ""
    for path, content in test_code.items():
        lines = content.splitlines()
        trimmed = "\n".join(lines[:100])
        test_context += f"\n── {path} ──\n{trimmed}"

    return f"""## Test Failures
{failure_lines or "See error trace below"}

## Error Trace (from pytest)
{error_trace[:3000]}

## Test Code
{test_context or "Not available"}

## All Project Files
{files_context}

Identify which file has the bug, then fix it.

YOUR RESPONSE MUST follow this EXACT format:
BUGGY_FILE: <exact file_path from the list above>
---FIXED_CODE_START---
<complete fixed file content here>
---FIXED_CODE_END---

Rules:
- Fix only ONE file — the root cause of the failure.
- Make the MINIMUM change needed.
- The fixed code must be a complete drop-in replacement.
- No markdown fences inside the fixed code section.
""".strip()


# ─────────────────────────────────────────────────────────────────────────────
# 4. Response parsing
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


def _parse_unidentified_response(
    raw: str,
    code_files: dict[str, str],
) -> tuple[str, str] | None:
    """
    Parse structured response when LLM was asked to identify + fix a file.
    Returns (file_path, fixed_code) or None if parsing fails.
    """
    # Extract file path
    file_match = re.search(r"BUGGY_FILE:\s*(.+?)$", raw, re.MULTILINE)
    if not file_match:
        return None

    file_path = file_match.group(1).strip()

    # Extract code between markers
    code_match = re.search(
        r"---FIXED_CODE_START---\s*\n(.*?)\n\s*---FIXED_CODE_END---",
        raw,
        re.DOTALL,
    )
    if not code_match:
        return None

    fixed_code = _extract_code(code_match.group(1).strip())

    # Validate file_path exists in code_files (try exact then basename match)
    if file_path not in code_files:
        from pathlib import Path

        basename = Path(file_path).name
        for existing in code_files:
            if Path(existing).name == basename:
                file_path = existing
                break
        else:
            return None

    return file_path, fixed_code


# ─────────────────────────────────────────────────────────────────────────────
# 5. Main agent entry point
# ─────────────────────────────────────────────────────────────────────────────

async def run(state: AutoDevState) -> AutoDevState:
    """
    Orchestrator is function ko call karta hai:
        from agents.debugger_agent import run as debugger_run
        state = await debugger_run(state)

    Steps:
        1. error_trace se buggy file identify karo
        2. LLM se targeted fix lo
        3. code_files mein sirf buggy file update karo
        4. retry_count increment karo
    """
    log(state, "Debugger", f"Agent started (attempt {state['retry_count'] + 1})")
    run_id = state["run_id"]

    error_trace: str = state.get("error_trace") or ""
    code_files: dict = state.get("code_files") or {}
    test_code: dict = state.get("test_code") or {}
    test_results: dict = state.get("test_results") or {}
    total_tokens: int = state.get("total_tokens", 0)

    failures: list = test_results.get("failures", [])

    # ── Guards ────────────────────────────────────────────────────────────────
    if not error_trace:
        log(state, "Debugger", "ERROR: no error_trace — nothing to debug")
        state["retry_count"] += 1
        return state

    if not code_files:
        log(state, "Debugger", "ERROR: code_files empty — nothing to fix")
        state["retry_count"] += 1
        return state

    # ── Step 1: Identify the buggy file ───────────────────────────────────────
    buggy_file = _identify_buggy_file(error_trace, code_files)

    if buggy_file:
        # ── Path A: Known buggy file — targeted fix ──────────────────────────
        log(state, "Debugger", f"Identified buggy file: {buggy_file}")

        user_prompt = _build_targeted_prompt(
            buggy_file, code_files[buggy_file], error_trace, test_code, failures,
        )
        messages = build_messages(_SYSTEM_PROMPT, user_prompt)

        try:
            llm_result = await call_llm(
                agent=AgentName.DEBUGGER,
                messages=messages,
                temperature=0.1,
                max_tokens=4096,
                run_id=run_id,
            )
        except RuntimeError as e:
            log(state, "Debugger", f"LLM call failed: {e}")
            state["retry_count"] += 1
            state["total_tokens"] = total_tokens
            return state

        raw = str(llm_result["content"])
        fixed_code = _extract_code(raw)
        code_files[buggy_file] = fixed_code

        tokens_used = int(llm_result.get("total_tokens", 0))
        total_tokens += tokens_used

        log(
            state, "Debugger",
            f"Fixed: {buggy_file} ({len(fixed_code)} chars, {tokens_used} tokens)",
        )

    else:
        # ── Path B: Can't identify file — ask LLM to find + fix ──────────────
        log(state, "Debugger", "Could not identify buggy file from trace — asking LLM")

        user_prompt = _build_unidentified_prompt(
            code_files, error_trace, test_code, failures,
        )
        messages = build_messages(_SYSTEM_PROMPT, user_prompt)

        try:
            llm_result = await call_llm(
                agent=AgentName.DEBUGGER,
                messages=messages,
                temperature=0.1,
                max_tokens=4096,
                run_id=run_id,
            )
        except RuntimeError as e:
            log(state, "Debugger", f"LLM call failed: {e}")
            state["retry_count"] += 1
            state["total_tokens"] = total_tokens
            return state

        raw = str(llm_result["content"])
        tokens_used = int(llm_result.get("total_tokens", 0))
        total_tokens += tokens_used

        parsed = _parse_unidentified_response(raw, code_files)
        if parsed:
            file_path, fixed_code = parsed
            code_files[file_path] = fixed_code
            log(
                state, "Debugger",
                f"LLM identified + fixed: {file_path} ({len(fixed_code)} chars)",
            )
        else:
            log(state, "Debugger", "WARNING: Could not parse LLM response — no fix applied")

    # ── Step 2: Save to state ─────────────────────────────────────────────────
    state["code_files"] = code_files
    state["retry_count"] += 1
    state["total_tokens"] = total_tokens

    log(state, "Debugger", f"Done | retry_count now {state['retry_count']}")

    return state
