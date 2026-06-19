"""
api/routes/runs.py
------------------
REST endpoints for project runs — aligned with MASTER_PROJECT_SPECIFICATION.

Endpoints:
    POST   /api/v1/projects/create       — Start a new pipeline run
    GET    /api/v1/projects/{run_id}      — Get run status
    GET    /api/v1/projects/{run_id}/logs — Get run logs
    GET    /api/v1/projects/{run_id}/download — Download ZIP
    GET    /api/v1/projects/history       — List all runs
    GET    /api/v1/health                 — Health check
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_db
from db.models import Run, User
from graph.state import create_initial_state, RunStatus
from tools.db_delivery import save_state_to_db, get_run_from_db

logger = logging.getLogger("agentic-platform")

router = APIRouter()

# Default anonymous user UUID — used when no user_id is provided.
ANONYMOUS_USER_ID = "00000000-0000-0000-0000-000000000000"


# ── Request / Response schemas ───────────────────────────────────────────

class CreateProjectRequest(BaseModel):
    prd: str = Field(..., min_length=10, description="Natural language project requirement")
    user_id: Optional[str] = Field(default=None, description="User ID (optional for now)")


class CreateProjectResponse(BaseModel):
    success: bool
    run_id: str


class RunStatusResponse(BaseModel):
    run_id: str
    status: str


class ErrorResponse(BaseModel):
    success: bool = False
    error: dict


# ── Helpers ──────────────────────────────────────────────────────────────

async def _ensure_user_exists(db: AsyncSession, user_id: str) -> None:
    """Create the user row if it doesn't exist yet (idempotent)."""
    result = await db.execute(select(User).where(User.id == user_id))
    if result.scalar_one_or_none() is None:
        db.add(User(id=user_id, email=f"{user_id}@placeholder.local", name="Anonymous"))
        await db.commit()


# ── Background pipeline runner ───────────────────────────────────────────

async def _run_pipeline_background(run_id: str, state: dict) -> None:
    """Run the agent pipeline in background. Saves final state to DB."""
    try:
        from graph.orchestrator import run_pipeline
        final_state = await run_pipeline(state)
        await save_state_to_db(final_state)
    except Exception as exc:
        logger.error("Background pipeline crashed | run_id=%s error=%s", run_id, exc)
        state["status"] = RunStatus.FAILED
        state["logs"].append(f"[FATAL] Pipeline crashed: {exc}")
        await save_state_to_db(state)


# ── Endpoints ────────────────────────────────────────────────────────────

@router.post("/projects/create", response_model=CreateProjectResponse)
async def create_project(req: CreateProjectRequest, db: AsyncSession = Depends(get_db)):
    """Accept a PRD, create a run, and kick off the agent pipeline."""
    run_id = str(uuid.uuid4())
    user_id = req.user_id or ANONYMOUS_USER_ID

    # Ensure the user row exists so the FK constraint is satisfied
    await _ensure_user_exists(db, user_id)

    state = create_initial_state(run_id=run_id, user_id=user_id, prd_text=req.prd)

    # Persist the initial run record
    await save_state_to_db(state)

    # Fire-and-forget: run pipeline in background
    asyncio.create_task(_run_pipeline_background(run_id, state))

    logger.info("Run created | run_id=%s user_id=%s", run_id, user_id)
    return CreateProjectResponse(success=True, run_id=run_id)


@router.get("/projects/history")
async def project_history(db: AsyncSession = Depends(get_db)):
    """List all runs (most recent first)."""
    result = await db.execute(
        select(Run.id, Run.status, Run.created_at)
        .order_by(Run.created_at.desc())
    )
    projects = [
        {"run_id": str(row.id), "status": row.status}
        for row in result.all()
    ]
    return {"projects": projects}


@router.get("/projects/{run_id}")
async def get_run_status(run_id: str):
    """Get current status of a run."""
    run = await get_run_from_db(run_id)
    if not run:
        raise HTTPException(status_code=404, detail={"code": "RUN_NOT_FOUND", "message": "Run does not exist"})
    return {
        "run_id": str(run.id),
        "user_id": run.user_id,
        "prd_text": run.prd_text,
        "status": run.status,
        "research_output": run.research_output,
        "task_plan": run.task_plan,
        "code_files": run.code_files,
        "test_results": run.test_results,
        "review_result": run.review_result,
        "download_url": run.download_url,
        "retry_count": run.retry_count,
        "error_trace": run.error_trace,
        "total_tokens": run.total_tokens,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "updated_at": run.updated_at.isoformat() if run.updated_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
    }


@router.delete("/projects/{run_id}")
async def delete_project(run_id: str, db: AsyncSession = Depends(get_db)):
    """Delete a run from the database by run_id."""
    result = await db.execute(select(Run).where(Run.id == run_id))
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail={"code": "RUN_NOT_FOUND", "message": "Run does not exist"})
    
    await db.delete(run)
    await db.commit()
    logger.info("Run deleted | run_id=%s", run_id)
    return {"success": True, "message": f"Run {run_id} deleted successfully"}


@router.get("/projects/{run_id}/logs")
async def get_run_logs(run_id: str):
    """Get execution logs for a run."""
    run = await get_run_from_db(run_id)
    if not run:
        raise HTTPException(status_code=404, detail={"code": "RUN_NOT_FOUND", "message": "Run does not exist"})
    return {"logs": run.logs or []}


@router.get("/projects/{run_id}/download")
async def download_project(run_id: str):
    """Get download URL for the generated project ZIP."""
    run = await get_run_from_db(run_id)
    if not run:
        raise HTTPException(status_code=404, detail={"code": "RUN_NOT_FOUND", "message": "Run does not exist"})

    if not run.download_url:
        raise HTTPException(status_code=400, detail={"code": "NOT_READY", "message": "Project ZIP not yet generated"})
    return {"download_url": run.download_url}


@router.get("/health")
async def health_check():
    """Basic health check."""
    return {"status": "healthy"}
