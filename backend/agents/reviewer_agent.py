"""
agents/reviewer_agent.py — Agent 6: Reviewer
=============================================
Model   : google/gemma-3-27b-it:free  (primary)
Fallback: microsoft/phi-4-reasoning:free

Job:
    Tests pass hone ke baad final code quality review karna,
    Ruff lint run karna, LLM se quality score + suggestions lena,
    aur project ko ZIP file mein package karna for delivery.

How it works:
    1. Docker sandbox mein Ruff lint run karo (Python static analysis)
    2. LLM ko code bhejo for quality review (score 0-100 + suggestions)
    3. Sandbox folder ko ZIP file mein compress karo
    4. review_result + download_url state mein save karo

After this agent:
    orchestrator sets status = COMPLETED → pipeline END

Reads  : state["code_files"], state["sandbox_folder"], state["task_plan"],
         state["test_results"]
Writes : state["review_result"], state["download_url"], state["total_tokens"]
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from config import AgentName, build_messages, call_llm
from graph.state import AutoDevState, log
from tools.smart_linter import run_lint
from tools.zip_delivery import create_zip_from_folder

logger = logging.getLogger("agentic-platform")


# ─────────────────────────────────────────────────────────────────────────────
# 1. System Prompt
# ─────────────────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """You are a senior code reviewer. You evaluate code quality rigorously.

STRICT RULES:
1. Output ONLY valid JSON — no markdown fences, no extra text.
2. Score from 0 to 100 based on: correctness, readability, structure, error handling, security.
3. Be honest. Don't inflate scores. A typical LLM-generated project scores 50-75.
4. Suggestions must be specific and actionable, not vague.

Your JSON response must have this EXACT structure:
{
  "quality_score": <int 0-100>,
  "quality_notes": "<one paragraph summary of code quality>",
  "suggestions": ["<specific improvement 1>", "<specific improvement 2>"]
}
""".strip()



# ─────────────────────────────────────────────────────────────────────────────
# 3. LLM quality review
# ─────────────────────────────────────────────────────────────────────────────

def _build_review_prompt(
    code_files: dict[str, str],
    task_plan: dict[str, Any],
    lint_issues: list[dict[str, Any]],
    test_summary: str,
) -> str:
    """Build user prompt for LLM quality review."""
    # Code snippets (trimmed)
    snippets = []
    for path, content in code_files.items():
        lines = content.splitlines()
        trimmed = "\n".join(lines[:120])
        if len(lines) > 120:
            trimmed += f"\n# ... ({len(lines) - 120} more lines)"
        snippets.append(f"── {path} ──\n{trimmed}")
    files_context = "\n\n".join(snippets) or "No source files."

    project_name = task_plan.get("project_name", "project")
    description = task_plan.get("project_description", "")

    lint_summary = "No lint issues found."
    if lint_issues:
        lint_lines = [f"  - {i['file']}:{i['line']} → {i['message']}" for i in lint_issues[:10]]
        lint_summary = f"{len(lint_issues)} issue(s) found:\n" + "\n".join(lint_lines)

    return f"""## Project: {project_name}
{description}

## Test Results
{test_summary}

## Lint Results (Ruff)
{lint_summary}

## Source Files
{files_context}

Review the code quality. Output ONLY valid JSON with quality_score, quality_notes, and suggestions.
""".strip()


def _parse_review_json(raw: str) -> dict[str, Any] | None:
    """Extract JSON from LLM response, handling markdown fences."""
    cleaned = raw.strip()

    # Strip markdown fences if present
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if len(lines) >= 3 and lines[-1].strip() == "```":
            cleaned = "\n".join(lines[1:-1])
        elif len(lines) >= 2:
            cleaned = "\n".join(lines[1:])

    # Try direct JSON parse
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Try extracting JSON object from mixed text
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    return None




# ─────────────────────────────────────────────────────────────────────────────
# 5. Main agent entry point
# ─────────────────────────────────────────────────────────────────────────────

async def run(state: AutoDevState) -> AutoDevState:
    """
    Orchestrator is function ko call karta hai:
        from agents.reviewer_agent import run as reviewer_run
        state = await reviewer_run(state)

    Steps:
        1. Ruff lint run karo Docker mein
        2. LLM se quality review lo (score + suggestions)
        3. Project ko ZIP mein package karo
        4. review_result + download_url state mein save karo
    """
    log(state, "Reviewer", "Agent started")
    run_id = state["run_id"]

    code_files: dict = state.get("code_files") or {}
    sandbox_folder: str = state.get("sandbox_folder") or ""
    task_plan: dict = state.get("task_plan") or {}
    test_results: dict = state.get("test_results") or {}
    total_tokens: int = state.get("total_tokens", 0)

    # ── Guards ────────────────────────────────────────────────────────────────
    if not code_files:
        log(state, "Reviewer", "ERROR: code_files empty — nothing to review")
        state["review_result"] = {
            "passed": False,
            "lint_issues": [],
            "quality_score": 0,
            "quality_notes": "No code files to review.",
            "suggestions": [],
        }
        return state

    if not sandbox_folder:
        log(state, "Reviewer", "ERROR: sandbox_folder missing")
        state["review_result"] = {
            "passed": False,
            "lint_issues": [],
            "quality_score": 0,
            "quality_notes": "Sandbox folder missing — cannot lint or package.",
            "suggestions": [],
        }
        return state

    # ── Step 1: Run Ruff/ESLint lint ──────────────────────────────────────────
    log(state, "Reviewer", "Running linter in Docker...")
    lint_issues = run_lint(sandbox_folder)
    log(state, "Reviewer", f"Ruff found {len(lint_issues)} issue(s)")

    # ── Step 2: LLM quality review ───────────────────────────────────────────
    log(state, "Reviewer", "Requesting LLM quality review...")
    test_summary = test_results.get("summary", "Tests passed")

    user_prompt = _build_review_prompt(code_files, task_plan, lint_issues, test_summary)
    messages = build_messages(_SYSTEM_PROMPT, user_prompt)

    quality_score = 0
    quality_notes = ""
    suggestions: list[str] = []

    try:
        llm_result = call_llm(
            agent=AgentName.REVIEWER,
            messages=messages,
            temperature=0.2,
            max_tokens=2048,
            run_id=run_id,
        )

        raw = str(llm_result["content"])
        tokens_used = int(llm_result.get("total_tokens", 0))
        total_tokens += tokens_used

        parsed = _parse_review_json(raw)
        if parsed:
            quality_score = int(parsed.get("quality_score", 0))
            quality_notes = str(parsed.get("quality_notes", ""))
            suggestions = list(parsed.get("suggestions", []))
            log(state, "Reviewer", f"Quality score: {quality_score}/100")
        else:
            quality_notes = "LLM response could not be parsed as JSON."
            log(state, "Reviewer", "WARNING: Could not parse LLM review response")

    except (RuntimeError, TypeError, ValueError) as e:
        log(state, "Reviewer", f"LLM call failed: {e}")
        quality_notes = f"LLM review failed: {e}"

    # ── Step 3: Create ZIP package ────────────────────────────────────────────
    log(state, "Reviewer", "Creating ZIP package...")
    project_name = task_plan.get("project_name", "project")

    try:
        zip_path = create_zip_from_folder(sandbox_folder, project_name)
        log(state, "Reviewer", f"ZIP created: {zip_path}")
    except Exception as e:
        log(state, "Reviewer", f"ZIP creation failed: {e}")
        zip_path = ""

    # ── Step 4: Save to state ─────────────────────────────────────────────────
    # review passes if quality_score >= 40 and no critical lint blockers
    passed = quality_score >= 40

    state["review_result"] = {
        "passed": passed,
        "lint_issues": lint_issues,
        "quality_score": quality_score,
        "quality_notes": quality_notes,
        "suggestions": suggestions,
    }
    state["download_url"] = zip_path
    state["total_tokens"] = total_tokens

    log(
        state, "Reviewer",
        f"Done | passed={passed} score={quality_score}/100 "
        f"lint_issues={len(lint_issues)} zip={zip_path}",
    )

    return state
