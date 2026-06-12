"""
tools/db_delivery.py — Save Final State to PostgreSQL
======================================================
Pipeline complete hone ke baad final AutoDevState ko
PostgreSQL mein persist karta hai (upsert — create or update).

Orchestrator ya Reviewer agent isko call karta hai pipeline
ke end mein ya har major state change pe.

Usage:
    from tools.db_delivery import save_state_to_db, get_run_from_db

    # Save current state
    run = await save_state_to_db(state)

    # Fetch a run by ID
    run = await get_run_from_db("some-uuid")
"""

from __future__ import annotations

import logging
from typing import Any

from db.database import AsyncSessionLocal
from db.models import Run, save_run_from_state

logger = logging.getLogger("agentic-platform")


# ─────────────────────────────────────────────────────────────────────────────
# 1. Save state → DB
# ─────────────────────────────────────────────────────────────────────────────

async def save_state_to_db(state: dict[str, Any]) -> Run | None:
    """
    AutoDevState dict ko PostgreSQL mein save karta hai (upsert).

    Parameters
    ----------
    state : dict
        The current AutoDevState (or any dict with run_id, user_id, etc.)

    Returns
    -------
    Run ORM object on success, None on failure.
    """
    run_id = state.get("run_id", "???")

    try:
        async with AsyncSessionLocal() as session:
            async with session.begin():
                run = await save_run_from_state(session, state)

        logger.info(
            "State saved to DB | run_id=%s status=%s tokens=%s",
            run_id, state.get("status"), state.get("total_tokens", 0),
        )
        return run

    except Exception as e:
        logger.error("DB save failed | run_id=%s error=%s", run_id, e)
        return None


# ─────────────────────────────────────────────────────────────────────────────
# 2. Fetch run from DB
# ─────────────────────────────────────────────────────────────────────────────

async def get_run_from_db(run_id: str) -> Run | None:
    """
    Run ID se ek run record fetch karta hai.

    Parameters
    ----------
    run_id : str
        UUID of the pipeline run.

    Returns
    -------
    Run ORM object if found, None otherwise.
    """
    from sqlalchemy import select

    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Run).where(Run.id == run_id)
            )
            return result.scalar_one_or_none()

    except Exception as e:
        logger.error("DB fetch failed | run_id=%s error=%s", run_id, e)
        return None


# ─────────────────────────────────────────────────────────────────────────────
# 3. Update single field
# ─────────────────────────────────────────────────────────────────────────────

async def update_run_status(run_id: str, status: str) -> bool:
    """
    Sirf status field update karta hai — lightweight update
    for orchestrator to call between agent transitions.

    Returns True on success, False on failure.
    """
    from sqlalchemy import update

    try:
        async with AsyncSessionLocal() as session:
            async with session.begin():
                await session.execute(
                    update(Run).where(Run.id == run_id).values(status=status)
                )

        logger.info("Run status updated | run_id=%s status=%s", run_id, status)
        return True

    except Exception as e:
        logger.error(
            "DB status update failed | run_id=%s status=%s error=%s",
            run_id, status, e,
        )
        return False
