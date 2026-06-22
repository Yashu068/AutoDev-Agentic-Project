"""
config.py — Central configuration for agentic-platform
Handles: OpenRouter client, agent model routing, call_llm() with retry + fallback,
         LangSmith tracing, token tracking, structured logging.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from dotenv import load_dotenv
from openai import APIError, APITimeoutError, AsyncOpenAI

# ─────────────────────────────────────────────
# 0. Environment — load .env before anything else
# ─────────────────────────────────────────────
load_dotenv()


# ─────────────────────────────────────────────
# 1. Structured Logger
# ─────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("agentic-platform")


# ─────────────────────────────────────────────
# 2. LangSmith Tracing
# ─────────────────────────────────────────────
def _configure_langsmith() -> None:
    langchain_key = os.getenv("LANGCHAIN_API_KEY", "")
    if not langchain_key:
        logger.warning("LANGCHAIN_API_KEY not set — tracing disabled.")
        return
    os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
    os.environ.setdefault("LANGCHAIN_PROJECT", "agentic-platform")
    os.environ["LANGCHAIN_API_KEY"] = langchain_key
    logger.info(
        "LangSmith tracing enabled | project=%s",
        os.environ["LANGCHAIN_PROJECT"],
    )


_configure_langsmith()


# ─────────────────────────────────────────────
# 3. Agent Enum
# ─────────────────────────────────────────────
class AgentName(str, Enum):
    RESEARCH = "research"
    PLANNER  = "planner"
    CODER    = "coder"
    TESTER   = "tester"
    DEBUGGER = "debugger"
    REVIEWER = "reviewer"


# ─────────────────────────────────────────────
# 4. Model Registry — ordered list per agent (tried sequentially)
# ─────────────────────────────────────────────
AGENT_MODELS: dict[str, list[str]] = {
    AgentName.RESEARCH: [
        "google/gemma-4-31b-it:free",
        "openai/gpt-oss-120b:free",
        "qwen/qwen3-next-80b-a3b-instruct:free",
    ],
    AgentName.PLANNER: [
        "nvidia/nemotron-3-super-120b-a12b:free",
        "google/gemma-4-31b-it:free",
        "qwen/qwen3-next-80b-a3b-instruct:free",
    ],
    AgentName.CODER: [
        "cohere/north-mini-code:free",
        "poolside/laguna-m.1:free",
        "openai/gpt-oss-120b:free",
    ],
    AgentName.TESTER: [
        "cohere/north-mini-code:free",
        "qwen/qwen3-next-80b-a3b-instruct:free",
        "openai/gpt-oss-120b:free",
    ],
    AgentName.DEBUGGER: [
        "google/gemma-4-31b-it:free",
        "cohere/north-mini-code:free",
        "openai/gpt-oss-120b:free",
        "poolside/laguna-m.1:free",
    ],
    AgentName.REVIEWER: [
        "google/gemma-4-31b-it:free",
        "openai/gpt-oss-120b:free",
        "nvidia/nemotron-3-super-120b-a12b:free",
    ],
}


# ─────────────────────────────────────────────
# 5. OpenRouter Client (singleton)
# ─────────────────────────────────────────────
_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
_OPENROUTER_HEADERS: dict[str, str] = {
    "HTTP-Referer": "https://agentic-platform.dev",
    "X-Title": "Agentic Platform",
}

_async_client: Optional[AsyncOpenAI] = None


def get_async_client() -> AsyncOpenAI:
    global _async_client
    if _async_client is None:
        api_key = os.getenv("OPENROUTER_API_KEY", "")
        if not api_key:
            raise EnvironmentError(
                "OPENROUTER_API_KEY is missing. Add it to your .env file."
            )
        _async_client = AsyncOpenAI(
            api_key=api_key,
            base_url=_OPENROUTER_BASE_URL,
            default_headers=_OPENROUTER_HEADERS,
            timeout=120.0,
            max_retries=0,
        )
    return _async_client


# ─────────────────────────────────────────────
# 6. LLM Call — retry + primary/fallback routing
# ─────────────────────────────────────────────
_RETRYABLE_ERRORS = (APITimeoutError, APIError)
_MAX_RETRIES = 3
_RETRY_WAIT_BASE = 4  # seconds


async def _make_retrying_call(
    model: str,
    messages: list[dict[str, str]],
    temperature: float,
    max_tokens: int,
    run_id: Optional[str],
) -> dict[str, object]:
    last_err: Exception | None = None
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            t0 = time.perf_counter()
            response = await get_async_client().chat.completions.create(
                model=model,
                messages=messages,  # type: ignore[arg-type]
                temperature=temperature,
                max_tokens=max_tokens,
            )
            latency_ms = round((time.perf_counter() - t0) * 1000)
            content = response.choices[0].message.content or ""
            usage   = response.usage
            return {
                "content":           content,
                "model_used":        model,
                "prompt_tokens":     usage.prompt_tokens     if usage else 0,
                "completion_tokens": usage.completion_tokens if usage else 0,
                "total_tokens":      usage.total_tokens      if usage else 0,
                "latency_ms":        latency_ms,
                "run_id":            run_id,
            }
        except _RETRYABLE_ERRORS as err:
            last_err = err
            if attempt < _MAX_RETRIES:
                wait = min(_RETRY_WAIT_BASE * (2 ** (attempt - 1)), 30)
                logger.warning(
                    "LLM retry %d/%d | model=%s error=%s wait=%ss",
                    attempt, _MAX_RETRIES, model, err, wait,
                )
                await asyncio.sleep(wait)
            else:
                raise


async def call_llm(
    agent: AgentName,
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.2,
    max_tokens: int = 4096,
    run_id: Optional[str] = None,
) -> dict[str, object]:
    """
    Public interface for all agent LLM calls.
    Tries each model in AGENT_MODELS[agent] sequentially until one succeeds.
    """
    models = AGENT_MODELS[agent]
    last_err: Exception | None = None

    for i, model in enumerate(models):
        try:
            result = await _make_retrying_call(model, messages, temperature, max_tokens, run_id)
            logger.info(
                "LLM OK | agent=%s model=%s tokens=%s latency=%sms run_id=%s",
                agent.value, result["model_used"],
                result["total_tokens"], result["latency_ms"], run_id,
            )
            return result
        except Exception as err:
            last_err = err
            if i < len(models) - 1:
                logger.warning(
                    "LLM model %d/%d failed — trying next | agent=%s model=%s error=%s",
                    i + 1, len(models), agent.value, model, err,
                )
            else:
                logger.error(
                    "LLM FAILED (all %d models) | agent=%s last_model=%s error=%s",
                    len(models), agent.value, model, err,
                )

    raise RuntimeError(
        f"[{agent.value}] All {len(models)} models failed. "
        f"Tried: {', '.join(models)}. Last error: {last_err}"
    )


# ─────────────────────────────────────────────
# 7. build_messages helper
# ─────────────────────────────────────────────
def build_messages(
    system_prompt: str,
    user_prompt: str,
) -> list[dict[str, str]]:
    """Construct a standard [system, user] messages list for call_llm()."""
    return [
        {"role": "system", "content": system_prompt.strip()},
        {"role": "user",   "content": user_prompt.strip()},
    ]


# ─────────────────────────────────────────────
# 8. Environment validation — call once at app startup
# ─────────────────────────────────────────────
REQUIRED_ENV_VARS: list[str] = [
    "OPENROUTER_API_KEY",
    "TAVILY_API_KEY",
    "LANGCHAIN_API_KEY",
]


def validate_environment() -> None:
    """Fail-fast on startup if any required env var is missing."""
    missing = [k for k in REQUIRED_ENV_VARS if not os.getenv(k)]
    if missing:
        raise EnvironmentError(
            f"Missing required environment variables: {', '.join(missing)}. "
            "Check your .env file."
        )
    logger.info("Environment validated — all required keys present.")


# ─────────────────────────────────────────────
# 9. Settings — immutable single source of truth
# ─────────────────────────────────────────────
@dataclass(frozen=True)
class Settings:
    # API keys
    openrouter_api_key: str   = field(default_factory=lambda: os.getenv("OPENROUTER_API_KEY", ""))
    tavily_api_key:     str   = field(default_factory=lambda: os.getenv("TAVILY_API_KEY", ""))
    firecrawl_api_key:  str   = field(default_factory=lambda: os.getenv("FIRECRAWL_API_KEY", ""))
    langchain_api_key:  str   = field(default_factory=lambda: os.getenv("LANGCHAIN_API_KEY", ""))

    # Database
    database_url:       str   = field(default_factory=lambda: os.getenv("DATABASE_URL", "postgresql+asyncpg://localhost:5432/agentic"))
    redis_url:          str   = field(default_factory=lambda: os.getenv("REDIS_URL", "redis://localhost:6379"))

    # Docker sandbox hard limits
    sandbox_memory_mb:  int   = 256
    sandbox_timeout_s:  int   = 30
    sandbox_cpu_quota:  int   = 50000   # 50% of one CPU core

    # Agent limits
    max_debug_retries:  int   = 5
    max_tokens_default: int   = 4096
    llm_temperature:    float = 0.2

    # App
    environment:        str   = field(default_factory=lambda: os.getenv("ENVIRONMENT", "development"))
    log_level:          str   = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))


# Module-level singleton — import this everywhere
settings = Settings()

logger.info(
    "config.py loaded | env=%s log_level=%s",
    settings.environment,
    settings.log_level,
)