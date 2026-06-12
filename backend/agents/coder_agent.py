"""
agents/coder_agent.py — Agent 3: Coder
=======================================
Model   : nvidia/llama-3.3-nemotron-super-49b-v1:free  (primary)
Fallback: microsoft/phi-4-reasoning:free

Job:
    Planner ka task_plan (file blueprint) leke ek-ek file ka code likhna.
    Output: code_files dict {file_path: file_content} + sandbox_folder path.

How it works:
    1. task_plan["files"] se sorted file list nikalo (implementation_order ke hisaab se)
    2. Har file ke liye LLM ko call karo with:
       - Project context (PRD, tech stack, project structure)
       - Pehle likhi gayi files ka code (growing context)
       - Current file ki specific instructions (purpose, key_functions, dependencies)
    3. LLM se pure source code lo aur code_files dict mein save karo
    4. Sab files likhne ke baad sandbox_folder mein disk par write karo

Reads  : state["prd_text"], state["task_plan"], state["research_output"]
Writes : state["code_files"], state["sandbox_folder"], state["total_tokens"]
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from config import AgentName, build_messages, call_llm
from graph.state import AutoDevState, RunStatus, log

logger = logging.getLogger("agentic-platform")


# ─────────────────────────────────────────────────────────────────────────────
# 1. System Prompt
# ─────────────────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """You are an expert software engineer. You write clean, production-ready code.

STRICT RULES:
1. Output ONLY the raw file content — no markdown fences, no explanations, no preamble.
   Do NOT wrap your output in ```python ... ``` or any other code block.
2. Write COMPLETE, working code. Never use placeholders like "# TODO" or "pass".
3. Include proper imports at the top of every file.
4. Follow the language's standard conventions and best practices.
5. If the file is a config file (requirements.txt, package.json, Dockerfile, .env.example, etc.),
   output its exact content — no code comments explaining what it is.
6. Use the exact function/class names from key_functions.
7. Respect dependencies — if this file imports from another project file,
   use the exact paths and names from the already-written files.
""".strip()


def _build_user_prompt(
    file_task: dict[str, Any],
    project_context: str,
    written_files: dict[str, str],
) -> str:
    """
    Build the user prompt for generating one file.
    Includes project context + already-written files as reference.
    """
    # Show already-written files so LLM can import from them correctly
    written_context = ""
    if written_files:
        snippets = []
        for path, content in written_files.items():
            # Trim very long files to save tokens — keep first 120 lines
            lines = content.splitlines()
            trimmed = "\n".join(lines[:120])
            if len(lines) > 120:
                trimmed += f"\n# ... ({len(lines) - 120} more lines)"
            snippets.append(f"── {path} ──\n{trimmed}")
        written_context = "\n\n".join(snippets)

    deps_str = ", ".join(file_task.get("dependencies", [])) or "None"
    funcs_str = ", ".join(file_task.get("key_functions", [])) or "None"

    return f"""## Project Context
{project_context}

## Already Written Files (use these for correct imports)
{written_context or "No files written yet — this is the first file."}

## File To Write Now
- Path: {file_task["file_path"]}
- Language: {file_task["language"]}
- Purpose: {file_task["purpose"]}
- Dependencies (imports from): {deps_str}
- Key functions/classes to implement: {funcs_str}
- Context needed: {file_task.get("context_needed", "None")}

Write the COMPLETE file content now. Output ONLY the raw file — no markdown fences.
""".strip()


def _build_project_context(state: AutoDevState) -> str:
    """
    Build a one-time project overview string from PRD + task_plan metadata.
    """
    task_plan = state.get("task_plan") or {}
    research = state.get("research_output") or {}

    project_name = task_plan.get("project_name", "unknown")
    description = task_plan.get("project_description", "")
    tech_stack = task_plan.get("tech_stack", {})

    # Flatten tech_stack dict into readable list
    stack_items: list[str] = []
    if isinstance(tech_stack, dict):
        for category, items in tech_stack.items():
            if items:
                stack_items.append(f"  {category}: {', '.join(items)}")
    stack_str = "\n".join(stack_items) or "Not specified"

    # File listing from plan
    files = task_plan.get("files", [])
    file_listing = "\n".join(
        f"  {f['implementation_order']}. {f['file_path']} — {f['purpose']}"
        for f in files
    )

    return f"""Project: {project_name}
Description: {description}

Tech Stack:
{stack_str}

PRD Summary: {state.get("prd_text", "")[:500]}

Research Summary: {research.get("summary", "N/A")}

File Structure (ordered by implementation priority):
{file_listing}
""".strip()


# ─────────────────────────────────────────────────────────────────────────────
# 2. Code extraction — strip markdown fences if LLM adds them
# ─────────────────────────────────────────────────────────────────────────────

def _extract_code(raw: str) -> str:
    """
    Strip markdown code fences if present.
    LLM sometimes wraps output in ```lang ... ``` despite instructions.
    """
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        # Remove first line (```python) and last line (```)
        if len(lines) >= 3 and lines[-1].strip() == "```":
            cleaned = "\n".join(lines[1:-1])
        elif len(lines) >= 2:
            cleaned = "\n".join(lines[1:])
    return cleaned


# ─────────────────────────────────────────────────────────────────────────────
# 3. Write files to disk (sandbox folder)
# ─────────────────────────────────────────────────────────────────────────────

def _write_to_sandbox(code_files: dict[str, str], project_name: str) -> str:
    """
    Create a temp directory inside backend/sandbox/ and write all generated files to disk.
    Returns the sandbox folder path.
    """
    import uuid

    # Create local 'sandbox' folder under the backend directory
    base_dir = Path(__file__).parent.parent / "sandbox"
    base_dir.mkdir(parents=True, exist_ok=True)

    # Generate unique sandbox folder name
    unique_id = uuid.uuid4().hex[:8]
    sandbox_path = base_dir / f"autodev_{project_name}_{unique_id}"
    sandbox_path.mkdir(parents=True, exist_ok=True)

    for file_path, content in code_files.items():
        full_path = sandbox_path / file_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")

    logger.info("Sandbox created | path=%s files=%d", sandbox_path, len(code_files))
    return str(sandbox_path.resolve())


# ─────────────────────────────────────────────────────────────────────────────
# 4. Main agent entry point
# ─────────────────────────────────────────────────────────────────────────────

async def run(state: AutoDevState) -> AutoDevState:
    """
    Orchestrator is function ko call karta hai:
        from agents.coder_agent import run as coder_run
        state = await coder_run(state)

    Steps:
        1. task_plan se sorted file list nikalo
        2. Project context ek baar banao
        3. Har file ke liye LLM call karo (growing context ke sath)
        4. code_files dict + sandbox_folder state mein save karo
    """
    log(state, "Coder", "Agent started")
    run_id = state["run_id"]
    task_plan: dict = state.get("task_plan") or {}

    # ── Guard ────────────────────────────────────────────────────────────────
    if not task_plan or not task_plan.get("files"):
        log(state, "Coder", "ERROR: task_plan empty or has no files — cannot code")
        state["status"] = RunStatus.FAILED
        return state

    # ── Step 1: Sort files by implementation_order ────────────────────────────
    file_tasks: list[dict] = sorted(
        task_plan["files"],
        key=lambda f: f.get("implementation_order", 999),
    )

    log(state, "Coder", f"Writing {len(file_tasks)} files in order")

    # ── Step 2: Build project context (one-time) ──────────────────────────────
    project_context = _build_project_context(state)

    # ── Step 3: Generate each file via LLM ────────────────────────────────────
    code_files: dict[str, str] = state.get("code_files") or {}
    total_tokens: int = state.get("total_tokens", 0)

    for i, file_task in enumerate(file_tasks, start=1):
        file_path = file_task["file_path"]

        # Skip if already generated (preserves debugger fixes on retry)
        if file_path in code_files:
            log(state, "Coder", f"[{i}/{len(file_tasks)}] Skipping (already exists): {file_path}")
            continue

        log(state, "Coder", f"[{i}/{len(file_tasks)}] Generating: {file_path}")

        user_prompt = _build_user_prompt(file_task, project_context, code_files)
        messages = build_messages(_SYSTEM_PROMPT, user_prompt)

        try:
            llm_result = call_llm(
                agent=AgentName.CODER,
                messages=messages,
                temperature=0.1,
                max_tokens=4096,
                run_id=run_id,
            )
        except RuntimeError as e:
            log(state, "Coder", f"LLM call failed for {file_path}: {e}")
            state["status"] = RunStatus.FAILED
            state["total_tokens"] = total_tokens
            state["code_files"] = code_files  # save partial progress
            return state

        raw_code = str(llm_result["content"])
        clean_code = _extract_code(raw_code)
        code_files[file_path] = clean_code

        tokens_used = int(llm_result.get("total_tokens", 0))
        total_tokens += tokens_used

        log(
            state, "Coder",
            f"[{i}/{len(file_tasks)}] Done: {file_path} "
            f"({len(clean_code)} chars, {tokens_used} tokens)",
        )

    # ── Step 4: Write to sandbox folder ───────────────────────────────────────
    project_name = task_plan.get("project_name", "project")
    sandbox_folder = _write_to_sandbox(code_files, project_name)

    # ── Save to state ─────────────────────────────────────────────────────────
    state["code_files"] = code_files
    state["sandbox_folder"] = sandbox_folder
    state["total_tokens"] = total_tokens

    log(
        state, "Coder",
        f"Done | files={len(code_files)} sandbox={sandbox_folder} "
        f"total_tokens={total_tokens}",
    )

    return state
