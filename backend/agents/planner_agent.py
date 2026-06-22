"""
agents/planner_agent.py — Agent 2: Planner
===========================================
Model   : nvidia/llama-3.3-nemotron-super-49b-v1:free  (primary)
Fallback: microsoft/phi-4-reasoning:free
Job     : Convert research_output → strict Pydantic-validated task_plan
          with file blueprint + implementation order

Fixes applied vs first draft:
  1. run() is now async — orchestrator uses await
  2. call_llm() uses correct signature from config.py:
       call_llm(agent=AgentName.PLANNER, messages=[...], run_id=..., ...)
  3. Fallback handled by call_llm() itself — removed duplicate _call_with_fallback
  4. total_tokens tracked from llm_result["total_tokens"]
  5. Imports aligned: AgentName, build_messages from config
  6. log() helper from graph.state used (matches orchestrator pattern)
  7. RunStatus.PLANNING / planner_failed via string (state.status is str in state.py)
"""

from __future__ import annotations

import json
import logging
from typing import Any

from pydantic import BaseModel, Field, ValidationError, field_validator

from config import AgentName, build_messages, call_llm
from graph.state import AutoDevState, RunStatus, log

logger = logging.getLogger("agentic-platform")


# ─────────────────────────────────────────────────────────────────────────────
# Pydantic Models — strict blueprint validation
# ─────────────────────────────────────────────────────────────────────────────

class FileTask(BaseModel):
    """One file the Coder agent will write."""

    file_path: str = Field(
        ...,
        description="Relative path from project root, e.g. 'backend/api/main.py'",
    )
    language: str = Field(
        ...,
        description="python | javascript | typescript | html | css | json | yaml | other",
    )
    purpose: str = Field(
        ...,
        description="One-sentence description of what this file does",
    )
    dependencies: list[str] = Field(
        default_factory=list,
        description="file_paths (within this project) that this file imports from",
    )
    implementation_order: int = Field(
        ...,
        ge=1,
        description="1-based integer — Coder writes lower numbers first",
    )
    key_functions: list[str] = Field(
        default_factory=list,
        description="Important function/class names the Coder must implement",
    )
    context_needed: str = Field(
        default="",
        description="Specific domain facts from research the Coder must know",
    )

    @field_validator("file_path")
    @classmethod
    def no_leading_slash(cls, v: str) -> str:
        return v.lstrip("/")

    @field_validator("language")
    @classmethod
    def lowercase_lang(cls, v: str) -> str:
        return v.lower().strip()


class TechStack(BaseModel):
    backend:  list[str] = Field(default_factory=list)
    frontend: list[str] = Field(default_factory=list)
    database: list[str] = Field(default_factory=list)
    devops:   list[str] = Field(default_factory=list)
    testing:  list[str] = Field(default_factory=list)
    other:    list[str] = Field(default_factory=list)


class TaskPlan(BaseModel):
    """
    Complete project blueprint.
    Stored as dict in AutoDevState["task_plan"].
    """

    project_name:        str            = Field(..., description="slug-style, e.g. 'todo-api'")
    project_description: str            = Field(..., description="2-3 sentence summary")
    tech_stack:          TechStack
    files:               list[FileTask] = Field(..., min_length=1)
    setup_commands:      list[str]      = Field(default_factory=list)
    env_variables:       list[str]      = Field(default_factory=list)
    total_files:         int            = Field(..., ge=1)
    estimated_complexity: str           = Field(..., description="low | medium | high")
    notes:               str            = Field(default="")

    @field_validator("files")
    @classmethod
    def fix_and_sort_orders(cls, files: list[FileTask]) -> list[FileTask]:
        """Auto-fix duplicate implementation_order values, then sort."""
        orders = [f.implementation_order for f in files]
        if len(orders) != len(set(orders)):
            for i, f in enumerate(
                sorted(files, key=lambda x: x.implementation_order), start=1
            ):
                f.implementation_order = i
        return sorted(files, key=lambda x: x.implementation_order)

    @field_validator("total_files")
    @classmethod
    def sync_total(cls, v: int, info: Any) -> int:
        files = info.data.get("files", [])
        return len(files) if files else v

    @field_validator("estimated_complexity")
    @classmethod
    def valid_complexity(cls, v: str) -> str:
        v = v.lower().strip()
        return v if v in {"low", "medium", "high"} else "medium"


# ─────────────────────────────────────────────────────────────────────────────
# Prompts
# ─────────────────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """You are an expert software architect and project planner.
Read the research output and produce a COMPLETE, ordered file blueprint that a
code-writing AI can follow exactly.

STRICT RULES:
1. Output ONLY valid JSON — no markdown fences, no explanation, no extra text.
2. List EVERY file: source code, config, requirements.txt/package.json,
   Dockerfile, .env.example, README.md, etc.
3. implementation_order — 1-based integers, NO duplicates.
   Dependencies must always have a LOWER order number than files that import them.
4. key_functions — list real function/class names, not vague descriptions.
5. context_needed — copy specific facts from the research the coder needs.
6. Do NOT invent technology absent from the research.

OUTPUT FORMAT (strict JSON, no fences):
{
  "project_name": "...",
  "project_description": "...",
  "tech_stack": {
    "backend": [...], "frontend": [...], "database": [...],
    "devops": [...], "testing": [...], "other": [...]
  },
  "files": [
    {
      "file_path": "...",
      "language": "...",
      "purpose": "...",
      "dependencies": [...],
      "implementation_order": 1,
      "key_functions": [...],
      "context_needed": "..."
    }
  ],
  "setup_commands": [...],
  "env_variables": [...],
  "total_files": <int>,
  "estimated_complexity": "low|medium|high",
  "notes": "..."
}"""


def _build_user_prompt(prd_text: str, research_output: dict) -> str:
    research_str = json.dumps(research_output, indent=2, ensure_ascii=False)
    return (
        f"## Original Requirement (PRD)\n{prd_text}\n\n"
        f"## Research Output (from Research Agent)\n{research_str}\n\n"
        "Produce the complete JSON task plan now.\n"
        "Remember: output ONLY JSON — no markdown fences, no explanation."
    )


# ─────────────────────────────────────────────────────────────────────────────
# JSON + Pydantic parser
# ─────────────────────────────────────────────────────────────────────────────

def _parse_and_validate(raw: str, run_id: str) -> tuple[TaskPlan | None, str]:
    """
    Strips markdown fences → JSON parse → Pydantic validate.
    Returns (TaskPlan, "") on success or (None, error_str) on failure.
    """
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = "\n".join(
            line for line in cleaned.splitlines()
            if not line.strip().startswith("```")
        ).strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.error("[%s] Planner JSON parse error: %s", run_id, e)
        return None, f"JSON parse error: {e}"

    try:
        return TaskPlan(**data), ""
    except ValidationError as e:
        logger.error("[%s] Planner Pydantic validation error: %s", run_id, e)
        return None, f"Validation error: {e}"


# ─────────────────────────────────────────────────────────────────────────────
# Main agent entry point
# ─────────────────────────────────────────────────────────────────────────────

_MAX_LLM_RETRIES = 2   # retry if LLM returns bad JSON / fails validation


async def run(state: AutoDevState) -> AutoDevState:
    """
    LangGraph node — called by orchestrator as:
        from agents.planner_agent import run as planner_run
        state = await planner_run(state)

    Reads  : state["prd_text"], state["research_output"]
    Writes : state["task_plan"], state["total_tokens"], state["logs"]
    """
    run_id: str  = state["run_id"]
    prd_text: str = state.get("prd_text", "")
    research_output: dict = state.get("research_output", {})

    log(state, "Planner", f"Agent 2 started — run_id={run_id}")

    # ── Guard ────────────────────────────────────────────────────────────────
    if not research_output:
        log(state, "Planner", "ERROR: research_output empty — cannot plan")
        return {**state, "status": RunStatus.FAILED}

    # ── Build prompts ────────────────────────────────────────────────────────
    system_prompt = _SYSTEM_PROMPT
    user_prompt   = _build_user_prompt(prd_text, research_output)

    task_plan: TaskPlan | None = None
    last_error = ""
    total_tokens: int = state.get("total_tokens", 0)

    # ── Retry loop ───────────────────────────────────────────────────────────
    for attempt in range(1, _MAX_LLM_RETRIES + 1):
        log(state, "Planner", f"LLM attempt {attempt}/{_MAX_LLM_RETRIES}")

        try:
            # ✅ Uses config.py call_llm() signature exactly:
            #    call_llm(agent, messages, *, temperature, max_tokens, run_id)
            #    Fallback is handled automatically inside call_llm()
            llm_result = await call_llm(
                agent=AgentName.PLANNER,
                messages=build_messages(system_prompt, user_prompt),
                temperature=0.1,      # low temp → deterministic JSON
                max_tokens=4096,
                run_id=run_id,
            )
        except RuntimeError as e:
            # Both primary + fallback failed
            last_error = str(e)
            log(state, "Planner", f"LLM call failed (attempt {attempt}): {e}")
            continue

        # Track tokens across all calls
        total_tokens += llm_result.get("total_tokens", 0)

        raw_output: str = llm_result["content"]  # type: ignore[assignment]
        log(
            state, "Planner",
            f"LLM responded — model={llm_result['model_used']} "
            f"tokens={llm_result['total_tokens']} latency={llm_result['latency_ms']}ms",
        )

        task_plan, last_error = _parse_and_validate(raw_output, run_id)

        if task_plan is not None:
            log(
                state, "Planner",
                f"Validation OK — {task_plan.total_files} files, "
                f"complexity={task_plan.estimated_complexity}",
            )
            break

        # Inject error into next prompt so LLM self-corrects
        log(state, "Planner", f"Validation failed: {last_error} — retrying")
        user_prompt = (
            user_prompt
            + f"\n\nYOUR PREVIOUS RESPONSE HAD THIS ERROR:\n{last_error}\n"
            + "Fix it and output ONLY valid JSON."
        )

    # ── Failure path ─────────────────────────────────────────────────────────
    if task_plan is None:
        log(
            state, "Planner",
            f"FAILED after {_MAX_LLM_RETRIES} attempts. Last error: {last_error}",
        )
        return {
            **state,
            "status":       RunStatus.FAILED,
            "total_tokens": total_tokens,
        }

    # ── Success path ─────────────────────────────────────────────────────────
    log(
        state, "Planner",
        f"Plan saved — project='{task_plan.project_name}' "
        f"files={len(task_plan.files)}",
    )

    return {
        **state,
        "task_plan":    task_plan.model_dump(),   # dict → LangGraph serializable
        "status":       RunStatus.PLANNING,
        "total_tokens": total_tokens,
    }