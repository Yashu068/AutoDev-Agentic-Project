"""
config.py — Central configuration for agentic-platform
Handles: OpenRouter client, agent model routing, call_llm() with retry + fallback,
         LangSmith tracing, token tracking, structured logging.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from dotenv import load_dotenv
from openai import APIError, APITimeoutError, OpenAI, RateLimitError
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

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
# 4. Model Registry — primary + fallback per agent
# ─────────────────────────────────────────────
AGENT_MODELS: dict[str, dict[str, str]] = {
    AgentName.RESEARCH: {
        "primary":  "google/gemma-3-27b-it:free",
        "fallback": "microsoft/phi-4-reasoning:free",
    },
    AgentName.PLANNER: {
        "primary":  "nvidia/llama-3.3-nemotron-super-49b-v1:free",
        "fallback": "microsoft/phi-4-reasoning:free",
    },
    AgentName.CODER: {
        "primary":  "nvidia/llama-3.3-nemotron-super-49b-v1:free",
        "fallback": "microsoft/phi-4-reasoning:free",
    },
    AgentName.TESTER: {
        "primary":  "meta-llama/llama-3.3-70b-instruct:free",
        "fallback": "microsoft/phi-4-reasoning:free",
    },
    AgentName.DEBUGGER: {
        "primary":  "nvidia/llama-3.3-nemotron-super-49b-v1:free",
        "fallback": "microsoft/phi-4-reasoning:free",
    },
    AgentName.REVIEWER: {
        "primary":  "google/gemma-3-27b-it:free",
        "fallback": "microsoft/phi-4-reasoning:free",
    },
}


# ─────────────────────────────────────────────
# 5. OpenRouter Client (singleton)
# ─────────────────────────────────────────────
_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
_OPENROUTER_HEADERS: dict[str, str] = {
    "HTTP-Referer": "https://agentic-platform.dev",
    "X-Title": "Agentic Platform",
}

_client: Optional[OpenAI] = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        api_key = os.getenv("OPENROUTER_API_KEY", "")
        if not api_key:
            raise EnvironmentError(
                "OPENROUTER_API_KEY is missing. Add it to your .env file."
            )
        _client = OpenAI(
            api_key=api_key,
            base_url=_OPENROUTER_BASE_URL,
            default_headers=_OPENROUTER_HEADERS,
            timeout=120.0,
            max_retries=0,
        )
    return _client


# ─────────────────────────────────────────────
# 6. LLM Call — retry + primary/fallback routing
# ─────────────────────────────────────────────
_RETRYABLE_ERRORS = (APITimeoutError, APIError)


def _make_retrying_call(
    model: str,
    messages: list[dict[str, str]],
    temperature: float,
    max_tokens: int,
    run_id: Optional[str],
) -> dict[str, object]:
    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=4, max=30),
        retry=retry_if_exception_type(_RETRYABLE_ERRORS),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def _call() -> dict[str, object]:
        t0 = time.perf_counter()
        response = get_client().chat.completions.create(
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

    return _call()  # type: ignore[return-value]


def call_llm(
    agent: AgentName,
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.2,
    max_tokens: int = 4096,
    run_id: Optional[str] = None,
    force_fallback: bool = False,
) -> dict[str, object]:
    """
    Public interface for all agent LLM calls.

    Parameters
    ----------
    agent          : AgentName enum — routes to correct model pair.
    messages       : OpenAI-format [{"role": ..., "content": ...}].
    temperature    : Sampling temperature. Default 0.2 = deterministic.
    max_tokens     : Max completion tokens.
    run_id         : LangGraph run_id for trace correlation.
    force_fallback : Skip primary, use fallback directly (for tests).

    Returns
    -------
    dict with keys: content, model_used, prompt_tokens, completion_tokens,
                    total_tokens, latency_ms, run_id
    """
    config   = AGENT_MODELS[agent]
    primary  = config["primary"]
    fallback = config["fallback"]
    first    = fallback if force_fallback else primary

    try:
        result = _make_retrying_call(first, messages, temperature, max_tokens, run_id)
        logger.info(
            "LLM OK | agent=%s model=%s tokens=%s latency=%sms run_id=%s",
            agent.value, result["model_used"],
            result["total_tokens"], result["latency_ms"], run_id,
        )
        return result

    except Exception as primary_err:
        if force_fallback or first == fallback:
            logger.error(
                "LLM FAILED | agent=%s model=%s error=%s",
                agent.value, first, primary_err,
            )
            raise RuntimeError(
                f"[{agent.value}] Model {first} failed after retries. "
                f"Error: {primary_err}"
            ) from primary_err

        logger.warning(
            "LLM primary failed — switching to fallback | agent=%s "
            "primary=%s fallback=%s error=%s",
            agent.value, primary, fallback, primary_err,
        )

        try:
            result = _make_retrying_call(
                fallback, messages, temperature, max_tokens, run_id
            )
            logger.info(
                "LLM FALLBACK OK | agent=%s model=%s tokens=%s latency=%sms",
                agent.value, result["model_used"],
                result["total_tokens"], result["latency_ms"],
            )
            return result

        except Exception as fallback_err:
            logger.error(
                "LLM FAILED (both) | agent=%s primary=%s fallback=%s error=%s",
                agent.value, primary, fallback, fallback_err,
            )
            raise RuntimeError(
                f"[{agent.value}] Both primary ({primary}) and fallback "
                f"({fallback}) failed. Last error: {fallback_err}"
            ) from fallback_err


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