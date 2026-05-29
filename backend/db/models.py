"""
db/models.py
------------
SQLAlchemy ORM models.
Two tables for now: User and Run.
All columns use snake_case; JSON blobs stored as JSONB (PostgreSQL).
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    String,
    Integer,
    Boolean,
    DateTime,
    Text,
    ForeignKey,
    func,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.database import Base


# ── User ──────────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    name: Mapped[str]  = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # One user → many runs
    runs: Mapped[list["Run"]] = relationship("Run", back_populates="user", lazy="select")

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email}>"


# ── Run ───────────────────────────────────────────────────────────────────────

class Run(Base):
    """
    One row = one complete pipeline execution.
    Mirrors AutoDevState so the full history is queryable from the dashboard.
    """
    __tablename__ = "runs"

    # ── Identity ──────────────────────────────────────────────────────────────
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    prd_text: Mapped[str] = mapped_column(Text, nullable=False)  # original requirement

    # ── Status ────────────────────────────────────────────────────────────────
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    # Values: pending | researching | planning | coding | testing |
    #         debugging | reviewing | completed | escalated | failed

    # ── Agent outputs (stored as JSONB — queryable, indexable) ────────────────
    research_output:  Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    task_plan:        Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    code_files:       Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # {file_path: file_content} — all generated source files

    test_results:     Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    review_result:    Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # ── Delivery ──────────────────────────────────────────────────────────────
    download_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    # Path to ZIP file on Railway volume or object store

    # ── Debug metadata ────────────────────────────────────────────────────────
    retry_count:  Mapped[int] = mapped_column(Integer, default=0)
    error_trace:  Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Observability ─────────────────────────────────────────────────────────
    logs:          Mapped[list | None] = mapped_column(ARRAY(Text), nullable=True, default=list)
    total_tokens:  Mapped[int] = mapped_column(Integer, default=0)

    # ── Timestamps ────────────────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # ── Relationship ──────────────────────────────────────────────────────────
    user: Mapped["User"] = relationship("User", back_populates="runs")

    def __repr__(self) -> str:
        return f"<Run id={self.id} status={self.status} user={self.user_id}>"


# ── Quick helpers (used by Reviewer agent / API routes) ───────────────────────

async def save_run_from_state(session, state: dict) -> Run:
    """
    Upsert a Run row from the current AutoDevState dict.
    Creates a new row on the first call; updates on subsequent calls.
    """
    from sqlalchemy import select
    from datetime import timezone

    result = await session.execute(select(Run).where(Run.id == state["run_id"]))
    run = result.scalar_one_or_none()

    if run is None:
        run = Run(id=state["run_id"], user_id=state["user_id"])
        session.add(run)

    # Sync all fields
    run.prd_text        = state["prd_text"]
    run.status          = state["status"]
    run.research_output = state.get("research_output")
    run.task_plan       = state.get("task_plan")
    run.code_files      = state.get("code_files")
    run.test_results    = state.get("test_results")
    run.review_result   = state.get("review_result")
    run.download_url    = state.get("download_url")
    run.retry_count     = state.get("retry_count", 0)
    run.error_trace     = state.get("error_trace")
    run.logs            = state.get("logs", [])
    run.total_tokens    = state.get("total_tokens", 0)

    if state["status"] in ("completed", "failed", "escalated"):
        run.completed_at = datetime.now(timezone.utc)

    await session.flush()
    return run