"""
api/main.py
-----------
FastAPI application entry point.
Start with: uvicorn api.main:app --reload
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import validate_environment
from db.database import init_db

logger = logging.getLogger("agentic-platform")


# ── Lifespan: runs once on startup / shutdown ────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: validate env + init DB. Shutdown: nothing special for now."""
    validate_environment()
    await init_db()
    logger.info("Database tables initialized.")
    logger.info("FastAPI startup complete.")
    yield
    logger.info("FastAPI shutdown.")


# ── App instance ─────────────────────────────────────────────────────────────

app = FastAPI(
    title="Agentic Platform API",
    version="1.0.0",
    description="Autonomous Multi-Agent Software Development Platform",
    lifespan=lifespan,
)


# ── CORS — allow React dev server ────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Register routes ──────────────────────────────────────────────────────────

from api.routes.runs import router as runs_router  # noqa: E402

app.include_router(runs_router, prefix="/api/v1")
