"""
db/database.py
--------------
Async SQLAlchemy engine + session factory.
Used by all DB operations (save run, fetch run, etc.).
"""

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncEngine,
    create_async_engine,
    async_sessionmaker,
)
from sqlalchemy.orm import DeclarativeBase
from typing import AsyncGenerator

from config import settings   # your existing config.py — must expose settings.database_url


# ── Engine ────────────────────────────────────────────────────────────────────

engine: AsyncEngine = create_async_engine(
    settings.database_url,       # e.g. "postgresql+asyncpg://user:pass@host/db"
    echo=False,                  # set True locally for SQL debug logs
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,          # drop stale connections automatically
)


# ── Session factory ───────────────────────────────────────────────────────────

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,      # keep objects usable after commit
    autoflush=False,
    autocommit=False,
)


# ── Base class for all ORM models ─────────────────────────────────────────────

class Base(DeclarativeBase):
    pass


# ── FastAPI dependency ────────────────────────────────────────────────────────

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Inject an async DB session into FastAPI route handlers.

    Usage in a route:
        @router.get("/runs/{run_id}")
        async def get_run(run_id: str, db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ── DB init (call once on startup) ───────────────────────────────────────────

async def init_db() -> None:
    """
    Creates all tables that are not yet present.
    Call from FastAPI lifespan / startup event.
    Does NOT drop or migrate existing tables — safe to call on every boot.
    """
    import db.models  # noqa: F401
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)