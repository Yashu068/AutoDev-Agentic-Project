"""
graph/orchestrator.py
---------------------
LangGraph pipeline — wires all 6 agents into a single StateGraph.

Flow:
    PRD → research → planner → coder → tester
                                           ↓
                                   passed? → reviewer → END (completed)
                                           ↓
                                   failed + retry < 3? → debugger → coder
                                           ↓
                                   failed + retry >= 3? → escalate → END (escalated)
"""

from __future__ import annotations

import logging
from typing import Literal

from langgraph.graph import StateGraph, END

from graph.state import AutoDevState, RunStatus, log

logger = logging.getLogger("agentic-platform")


# ─────────────────────────────────────────────────────────────────────────────
# 1.  Agent node imports  (will exist once each agent file is written)
# ─────────────────────────────────────────────────────────────────────────────
# Each agent module must expose one async function:
#     async def run(state: AutoDevState) -> AutoDevState
#
# Imports are done lazily inside each node function so that the graph can be
# imported and inspected even before all agent files are written.
# ─────────────────────────────────────────────────────────────────────────────


# ─────────────────────────────────────────────────────────────────────────────
# 2.  Node functions
# ─────────────────────────────────────────────────────────────────────────────

async def research_node(state: AutoDevState) -> AutoDevState:
    """Agent 1 — Web research → structured research_output JSON."""
    # Resume: skip if already completed
    if state.get("research_output"):
        log(state, "Orchestrator", "→ research_node SKIPPED (already done)")
        return state

    log(state, "Orchestrator", "→ research_node started")
    state["status"] = RunStatus.RESEARCHING

    from agents.research_agent import run as research_run
    state = await research_run(state)

    if state.get("status") != RunStatus.FAILED:
        state["last_completed_node"] = "research"
    log(state, "Orchestrator", "✓ research_node done")
    return state


async def planner_node(state: AutoDevState) -> AutoDevState:
    """Agent 2 — research_output → Pydantic-validated task_plan (file blueprint)."""
    # Resume: skip if already completed
    if state.get("task_plan"):
        log(state, "Orchestrator", "→ planner_node SKIPPED (already done)")
        return state

    log(state, "Orchestrator", "→ planner_node started")
    state["status"] = RunStatus.PLANNING

    from agents.planner_agent import run as planner_run
    state = await planner_run(state)

    if state.get("status") != RunStatus.FAILED:
        state["last_completed_node"] = "planner"
    log(state, "Orchestrator", "✓ planner_node done")
    return state


async def coder_node(state: AutoDevState) -> AutoDevState:
    """Agent 3 — task_plan → writes code file-by-file with growing context."""
    log(state, "Orchestrator", "→ coder_node started")
    state["status"] = RunStatus.CODING

    from agents.coder_agent import run as coder_run
    state = await coder_run(state)

    if state.get("status") != RunStatus.FAILED:
        state["last_completed_node"] = "coder"
    log(state, "Orchestrator", "✓ coder_node done")
    return state


async def tester_node(state: AutoDevState) -> AutoDevState:
    """Agent 4 — writes pytest tests + runs them in Docker sandbox."""
    log(state, "Orchestrator", "→ tester_node started")
    state["status"] = RunStatus.TESTING

    from agents.tester_agent import run as tester_run
    state = await tester_run(state)

    if state.get("status") != RunStatus.FAILED:
        state["last_completed_node"] = "tester"
    log(state, "Orchestrator", "✓ tester_node done")
    return state


async def debugger_node(state: AutoDevState) -> AutoDevState:
    """Agent 5 — reads error_trace, fixes ONE file via AST, increments retry_count."""
    log(state, "Orchestrator", f"→ debugger_node started (retry {state['retry_count']})")
    state["status"] = RunStatus.DEBUGGING

    from agents.debugger_agent import run as debugger_run
    state = await debugger_run(state)

    log(state, "Orchestrator", "✓ debugger_node done")
    return state


async def reviewer_node(state: AutoDevState) -> AutoDevState:
    """Agent 6 — Ruff/ESLint lint + quality review + ZIP delivery + DB save."""
    log(state, "Orchestrator", "→ reviewer_node started")
    state["status"] = RunStatus.REVIEWING

    from agents.reviewer_agent import run as reviewer_run
    state = await reviewer_run(state)

    state["status"] = RunStatus.COMPLETED
    log(state, "Orchestrator", "✓ reviewer_node done — pipeline COMPLETED")
    return state


async def escalate_node(state: AutoDevState) -> AutoDevState:
    """
    Terminal node when 3 debug retries all fail.
    Marks run as ESCALATED so a human can review it from the dashboard.
    """
    log(
        state,
        "Orchestrator",
        f"✗ 3 retries exhausted — escalating run {state['run_id']} for human review",
    )
    state["status"] = RunStatus.ESCALATED
    return state


# ─────────────────────────────────────────────────────────────────────────────
# 3.  Routing / conditional edges
# ─────────────────────────────────────────────────────────────────────────────

MAX_RETRIES = 5  # must match settings.max_debug_retries in config.py


def _is_failed(state: AutoDevState) -> bool:
    """Check if current state indicates a failed agent."""
    return state.get("status") == RunStatus.FAILED


def route_after_research(
    state: AutoDevState,
) -> Literal["planner", "escalate"]:
    if _is_failed(state):
        log(state, "Orchestrator", "Research FAILED → aborting pipeline")
        return "escalate"
    return "planner"


def route_after_planner(
    state: AutoDevState,
) -> Literal["coder", "escalate"]:
    if _is_failed(state):
        log(state, "Orchestrator", "Planner FAILED → aborting pipeline")
        return "escalate"
    return "coder"


def route_after_coder(
    state: AutoDevState,
) -> Literal["tester", "escalate"]:
    if _is_failed(state):
        log(state, "Orchestrator", "Coder FAILED → aborting pipeline")
        return "escalate"
    return "tester"


def route_after_tester(
    state: AutoDevState,
) -> Literal["reviewer", "debugger", "escalate"]:
    """
    Called after tester_node completes.

    Returns
    -------
    "reviewer"  — all tests passed → go to review + delivery
    "debugger"  — tests failed AND retry_count < MAX_RETRIES → attempt fix
    "escalate"  — tests failed AND retry_count >= MAX_RETRIES → human needed
    """
    if _is_failed(state):
        log(state, "Orchestrator", "Tester FAILED → aborting pipeline")
        return "escalate"

    test_results = state.get("test_results") or {}
    passed = test_results.get("passed", False)

    if passed:
        log(state, "Orchestrator", "Tests PASSED → routing to reviewer")
        return "reviewer"

    if state["retry_count"] < MAX_RETRIES:
        log(
            state,
            "Orchestrator",
            f"Tests FAILED — retry {state['retry_count'] + 1}/{MAX_RETRIES} → routing to debugger",
        )
        return "debugger"

    log(
        state,
        "Orchestrator",
        f"Tests FAILED — {MAX_RETRIES} retries exhausted → routing to escalate",
    )
    return "escalate"


# ─────────────────────────────────────────────────────────────────────────────
# 4.  Graph assembly
# ─────────────────────────────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    """
    Assembles and compiles the full LangGraph StateGraph.

    Node wiring:
        research → planner → coder → tester
                                        ↓ (conditional)
                                  reviewer → END
                                  debugger → coder   (retry loop)
                                  escalate → END
    """
    graph = StateGraph(AutoDevState)

    # ── Add nodes ─────────────────────────────────────────────────────────────
    graph.add_node("research",  research_node)
    graph.add_node("planner",   planner_node)
    graph.add_node("coder",     coder_node)
    graph.add_node("tester",    tester_node)
    graph.add_node("debugger",  debugger_node)
    graph.add_node("reviewer",  reviewer_node)
    graph.add_node("escalate",  escalate_node)

    # ── Entry point ───────────────────────────────────────────────────────────
    graph.set_entry_point("research")

    # ── Conditional edges (fail-fast if any agent sets FAILED) ─────────────────
    graph.add_conditional_edges("research", route_after_research,
        {"planner": "planner", "escalate": "escalate"})
    graph.add_conditional_edges("planner", route_after_planner,
        {"coder": "coder", "escalate": "escalate"})
    graph.add_conditional_edges("coder", route_after_coder,
        {"tester": "tester", "escalate": "escalate"})

    # ── Conditional edge after tester ─────────────────────────────────────────
    graph.add_conditional_edges(
        "tester",
        route_after_tester,
        {
            "reviewer": "reviewer",
            "debugger": "debugger",
            "escalate": "escalate",
        },
    )

    # ── Debugger loops back to coder ──────────────────────────────────────────
    graph.add_edge("debugger", "coder")

    # ── Terminal nodes ────────────────────────────────────────────────────────
    graph.add_edge("reviewer", END)
    graph.add_edge("escalate", END)

    return graph.compile()


# ─────────────────────────────────────────────────────────────────────────────
# 5.  Public singleton — import this everywhere
# ─────────────────────────────────────────────────────────────────────────────

pipeline = build_graph()


# ─────────────────────────────────────────────────────────────────────────────
# 6.  run_pipeline() — called by FastAPI route
# ─────────────────────────────────────────────────────────────────────────────

async def run_pipeline(initial_state: AutoDevState) -> AutoDevState:
    """
    Entry point for the FastAPI route handler.

    Parameters
    ----------
    initial_state : AutoDevState
        Created via graph.state.create_initial_state(run_id, user_id, prd_text)

    Returns
    -------
    AutoDevState — final state after the pipeline completes (or escalates).

    Usage in api/routes/runs.py:
        from graph.orchestrator import run_pipeline
        from graph.state import create_initial_state
        import uuid

        state = create_initial_state(
            run_id  = str(uuid.uuid4()),
            user_id = current_user.id,
            prd_text = request.prd_text,
        )
        final_state = await run_pipeline(state)
    """
    logger.info(
        "Pipeline START | run_id=%s user_id=%s",
        initial_state["run_id"],
        initial_state["user_id"],
    )

    try:
        final_state: AutoDevState = await pipeline.ainvoke(initial_state)  # type: ignore[assignment]
    except Exception as exc:
        logger.error(
            "Pipeline CRASHED | run_id=%s error=%s",
            initial_state["run_id"],
            exc,
            exc_info=True,
        )
        initial_state["status"] = RunStatus.FAILED
        initial_state["logs"].append(f"[FATAL] Pipeline crashed: {exc}")
        return initial_state

    logger.info(
        "Pipeline END | run_id=%s status=%s total_tokens=%s",
        final_state["run_id"],
        final_state["status"],
        final_state["total_tokens"],
    )
    return final_state


async def resume_pipeline(saved_state: AutoDevState) -> AutoDevState:
    """
    Resume a FAILED or ESCALATED pipeline from where it left off.
    Nodes that already produced output will be skipped automatically.

    Usage in api/routes/runs.py:
        from graph.orchestrator import resume_pipeline
        final_state = await resume_pipeline(saved_state)
    """
    run_id = saved_state["run_id"]
    last_node = saved_state.get("last_completed_node", "none")

    logger.info(
        "Pipeline RESUME | run_id=%s last_completed=%s",
        run_id, last_node,
    )

    # Reset status so routing functions don't see FAILED
    saved_state["status"] = RunStatus.PENDING
    saved_state["logs"].append(
        f"[RESUME] Retrying from after '{last_node}'"
    )

    return await run_pipeline(saved_state)