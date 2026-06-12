"""
graph/state.py
--------------
Shared state object that flows through all 6 agents in the LangGraph pipeline.
Every agent reads from and writes to this single TypedDict.
"""

from typing import TypedDict, Optional, List, Dict, Any
from enum import Enum


class RunStatus(str, Enum):
    PENDING    = "pending"
    RESEARCHING = "researching"
    PLANNING   = "planning"
    CODING     = "coding"
    TESTING    = "testing"
    DEBUGGING  = "debugging"
    REVIEWING  = "reviewing"
    COMPLETED  = "completed"
    ESCALATED  = "escalated"   # 3 retries failed → human review
    FAILED     = "failed"


class AutoDevState(TypedDict):
    # ── Identity ──────────────────────────────────────────────────────────────
    run_id:          str                        # UUID for this pipeline run
    user_id:         str                        # who triggered the run
    prd_text:        str                        # raw plain-English requirement

    # ── Agent 1 — Research ───────────────────────────────────────────────────
    research_output: Optional[Dict[str, Any]]
    # Shape written by Research agent:
    # {
    #   "summary":        str,
    #   "tech_stack":     List[str],
    #   "references":     List[{"url": str, "title": str, "snippet": str}],
    #   "similar_projects": List[str],
    #   "key_concepts":   List[str],
    # }

    # ── Agent 2 — Planner ────────────────────────────────────────────────────
    task_plan:       Optional[Dict[str, Any]]
    # Shape written by Planner agent (Pydantic-validated TaskPlan):
    # {
    #   "project_name":        str,
    #   "project_description": str,
    #   "tech_stack": {
    #       "backend": List[str], "frontend": List[str], "database": List[str],
    #       "devops": List[str],  "testing": List[str],  "other": List[str],
    #   },
    #   "files": [
    #     {
    #       "file_path":            str,         e.g. "backend/api/main.py"
    #       "language":             str,         e.g. "python"
    #       "purpose":              str,
    #       "dependencies":         List[str],   file_paths this file imports from
    #       "implementation_order": int,         1-based; lower = write first
    #       "key_functions":        List[str],
    #       "context_needed":       str,
    #     }
    #   ],
    #   "setup_commands":      List[str],
    #   "env_variables":       List[str],
    #   "total_files":         int,
    #   "estimated_complexity": str,             "low" | "medium" | "high"
    #   "notes":               str,
    # }

    # ── Agent 3 — Coder ──────────────────────────────────────────────────────
    code_files:      Optional[Dict[str, str]]   # {file_path: file_content}
    sandbox_folder:  Optional[str]              # temp dir path on host

    # ── Agent 4 — Tester ─────────────────────────────────────────────────────
    test_code:       Optional[Dict[str, str]]   # {test_file_path: content}
    test_results:    Optional[Dict[str, Any]]
    # Shape written by Tester agent:
    # {
    #   "passed":   bool,
    #   "summary":  str,
    #   "failures": [{"test": str, "error": str}],
    #   "stdout":   str,
    #   "stderr":   str,
    #   "exit_code": int,
    # }

    # ── Agent 5 — Debugger ───────────────────────────────────────────────────
    retry_count:     int                        # starts at 0, max 3
    error_trace:     Optional[str]              # last pytest stderr/stdout

    # ── Agent 6 — Reviewer ───────────────────────────────────────────────────
    review_result:   Optional[Dict[str, Any]]
    # Shape written by Reviewer agent:
    # {
    #   "passed":          bool,
    #   "lint_issues":     List[{"file": str, "line": int, "message": str}],
    #   "quality_score":   int,           0-100
    #   "quality_notes":   str,
    #   "suggestions":     List[str],
    # }
    download_url:    Optional[str]              # presigned URL or local path to ZIP

    # ── Metadata ─────────────────────────────────────────────────────────────
    status:          RunStatus
    logs:            List[str]                  # append-only list of log lines
    total_tokens:    int                        # cumulative across all LLM calls


# ── Helper: create a blank initial state ─────────────────────────────────────

def create_initial_state(run_id: str, user_id: str, prd_text: str) -> AutoDevState:
    """
    Call this once at the start of every pipeline run.
    Fills in all required fields with safe defaults so every
    agent can do `state["field"]` without KeyError.
    """
    return AutoDevState(
        run_id=run_id,
        user_id=user_id,
        prd_text=prd_text,

        research_output=None,
        task_plan=None,

        code_files=None,
        sandbox_folder=None,

        test_code=None,
        test_results=None,

        retry_count=0,
        error_trace=None,

        review_result=None,
        download_url=None,

        status=RunStatus.PENDING,
        logs=[],
        total_tokens=0,
    )


# ── Helper: append a log line ─────────────────────────────────────────────────

def log(state: AutoDevState, agent: str, message: str) -> None:
    """
    Mutates state["logs"] in-place.
    Usage inside any agent:
        log(state, "Planner", "Blueprint validated — 7 files to write")
    """
    from datetime import datetime
    entry = f"[{datetime.utcnow().isoformat(timespec='seconds')}] [{agent}] {message}"
    state["logs"].append(entry)
    print(entry)   # also surfaces in LangSmith trace