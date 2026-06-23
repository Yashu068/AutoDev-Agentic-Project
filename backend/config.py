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
#    Prefix format: "provider/model-name"
#    Providers: gemini, groq, openrouter
# ─────────────────────────────────────────────
AGENT_MODELS: dict[str, list[str]] = {
    # Research: needs large context + good summarization
    AgentName.RESEARCH: [
        "gemini/gemini-2.5-flash",
        "groq/llama-3.3-70b-versatile",
        "openrouter/google/gemma-4-31b-it:free",
    ],
    # Planner: needs strong reasoning + reliable JSON output
    AgentName.PLANNER: [
        "gemini/gemini-2.5-flash",
        "groq/llama-3.3-70b-versatile",
        "openrouter/nvidia/nemotron-3-super-120b-a12b:free",
    ],
    # Coder: needs strong code generation
    AgentName.CODER: [
        "groq/llama-3.3-70b-versatile",
        "gemini/gemini-2.5-flash",
        "openrouter/cohere/north-mini-code:free",
    ],
    # Tester: needs code understanding + test generation
    AgentName.TESTER: [
        "groq/llama-3.3-70b-versatile",
        "gemini/gemini-2.5-flash",
        "openrouter/qwen/qwen3-next-80b-a3b-instruct:free",
    ],
    # Debugger: needs reasoning over tracebacks + targeted code fixes
    AgentName.DEBUGGER: [
        "gemini/gemini-2.5-flash",
        "groq/llama-3.3-70b-versatile",
        "openrouter/google/gemma-4-31b-it:free",
    ],
    # Reviewer: needs evaluation + structured JSON scoring
    AgentName.REVIEWER: [
        "groq/llama-3.3-70b-versatile",
        "gemini/gemini-2.5-flash",
        "openrouter/google/gemma-4-31b-it:free",
    ],
}


# ─────────────────────────────────────────────
# 5. Multi-Provider Client Factory
#    Supported: openrouter, gemini, groq
# ─────────────────────────────────────────────
_PROVIDER_CONFIG = {
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "env_key": "OPENROUTER_API_KEY",
        "default_headers": {
            "HTTP-Referer": "https://agentic-platform.dev",
            "X-Title": "Agentic Platform",
        },
    },
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "env_key": "GEMINI_API_KEY",
        "default_headers": {},
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "env_key": "GROQ_API_KEY",
        "default_headers": {},
    },
}

_clients: dict[str, AsyncOpenAI] = {}


def _get_client(provider: str) -> AsyncOpenAI:
    """Get or create a cached AsyncOpenAI client for the given provider."""
    if provider in _clients:
        return _clients[provider]

    cfg = _PROVIDER_CONFIG.get(provider)
    if not cfg:
        raise ValueError(f"Unknown LLM provider: {provider}")

    api_key = os.getenv(cfg["env_key"], "")
    if not api_key:
        raise EnvironmentError(
            f"{cfg['env_key']} is missing. Add it to your .env file."
        )

    client = AsyncOpenAI(
        api_key=api_key,
        base_url=cfg["base_url"],
        default_headers=cfg["default_headers"] or None,
        timeout=120.0,
        max_retries=0,
    )
    _clients[provider] = client
    return client


def _parse_model_string(prefixed_model: str) -> tuple[str, str]:
    """
    Parse 'provider/model-name' → (provider, model_name).
    For openrouter models the model name itself contains slashes,
    e.g. 'openrouter/google/gemma-4-31b-it:free' → ('openrouter', 'google/gemma-4-31b-it:free').
    """
    for provider in _PROVIDER_CONFIG:
        prefix = f"{provider}/"
        if prefixed_model.startswith(prefix):
            return provider, prefixed_model[len(prefix):]
    # No prefix → default to openrouter (backward compat)
    return "openrouter", prefixed_model


# Backward-compatible alias used nowhere else but kept for safety
def get_async_client() -> AsyncOpenAI:
    return _get_client("openrouter")


# ─────────────────────────────────────────────
# 6. LLM Call — retry + multi-provider fallback
# ─────────────────────────────────────────────
_RETRYABLE_ERRORS = (APITimeoutError, APIError)
_MAX_RETRIES = 3          # for non-429 errors (timeouts, 500s)
_MAX_RPM_RETRIES = 3      # for 429 RPM — wait patiently, keep same model
_RETRY_WAIT_BASE = 4      # seconds
_DEFAULT_429_WAIT = 30    # fallback when no Retry-After is given


class DailyQuotaExhausted(Exception):
    """Raised when OpenRouter daily free-model quota (50/day) is used up."""
    pass


def _parse_429_error(err: APIError) -> tuple[bool, int]:
    """
    Parse a 429 error to determine type and wait time.
    Returns (is_daily_quota, retry_after_seconds).
    Works for all 3 providers: OpenRouter, Gemini, Groq.
    """
    err_str = str(err)

    # Daily quota — switch to next model
    if "free-models-per-day" in err_str:          # OpenRouter
        return True, 0
    if "FreeTier" in err_str and "PerDay" in err_str:  # Gemini
        return True, 0
    if "per day" in err_str.lower():              # Groq
        return True, 0

    retry_after = 0

    # 1. OpenRouter body metadata
    try:
        body = err.body or {}
        metadata = body.get("error", {}).get("metadata", {})
        retry_after = int(metadata.get("retry_after_seconds", 0))
    except (AttributeError, TypeError, ValueError):
        pass

    # 2. Standard HTTP Retry-After header (Gemini, Groq)
    if retry_after <= 0:
        try:
            header_val = err.response.headers.get("retry-after", "")
            if header_val:
                retry_after = int(header_val)
        except (AttributeError, TypeError, ValueError):
            pass

    # 3. Default floor — any 429 should wait meaningfully
    if retry_after <= 0:
        retry_after = _DEFAULT_429_WAIT

    return False, retry_after


async def _make_retrying_call(
    provider: str,
    model: str,
    messages: list[dict[str, str]],
    temperature: float,
    max_tokens: int,
    run_id: Optional[str],
) -> dict[str, object]:
    client = _get_client(provider)
    rpm_retries = 0
    other_retries = 0

    while True:
        try:
            t0 = time.perf_counter()
            response = await client.chat.completions.create(
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
                "model_used":        f"{provider}/{model}",
                "prompt_tokens":     usage.prompt_tokens     if usage else 0,
                "completion_tokens": usage.completion_tokens if usage else 0,
                "total_tokens":      usage.total_tokens      if usage else 0,
                "latency_ms":        latency_ms,
                "run_id":            run_id,
            }
        except _RETRYABLE_ERRORS as err:

            # ── 429 Rate Limit ────────────────────────────────────────
            if isinstance(err, APIError) and err.status_code == 429:
                is_daily, retry_after = _parse_429_error(err)

                # Daily quota → switch to next model
                if is_daily:
                    logger.error(
                        "Daily quota exhausted | provider=%s model=%s run_id=%s",
                        provider, model, run_id,
                    )
                    raise DailyQuotaExhausted(str(err)) from err

                # RPM limit → wait and retry same model
                rpm_retries += 1
                if rpm_retries > _MAX_RPM_RETRIES:
                    logger.error(
                        "RPM retries exhausted (%d/%d) | provider=%s model=%s",
                        rpm_retries, _MAX_RPM_RETRIES, provider, model,
                    )
                    raise

                wait = min(retry_after + 1, 120)
                logger.warning(
                    "RPM limit — waiting %ss then retrying (%d/%d) | provider=%s model=%s",
                    wait, rpm_retries, _MAX_RPM_RETRIES, provider, model,
                )
                await asyncio.sleep(wait)
                continue

            # ── Other errors (timeout, 500, etc) ──────────────────────
            other_retries += 1
            if other_retries > _MAX_RETRIES:
                raise

            wait = min(_RETRY_WAIT_BASE * (2 ** (other_retries - 1)), 30)
            logger.warning(
                "LLM transient error — retrying (%d/%d) | provider=%s model=%s error=%s wait=%ss",
                other_retries, _MAX_RETRIES, provider, model, err, wait,
            )
            await asyncio.sleep(wait)


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
    Automatically skips models whose provider API key is not configured.
    """
    models = AGENT_MODELS[agent]
    last_err: Exception | None = None

    for i, prefixed_model in enumerate(models):
        provider, model_name = _parse_model_string(prefixed_model)

        # Skip if API key for this provider is not set
        env_key = _PROVIDER_CONFIG[provider]["env_key"]
        if not os.getenv(env_key, ""):
            logger.warning(
                "Skipping model %s — %s not configured | agent=%s",
                prefixed_model, env_key, agent.value,
            )
            continue

        try:
            result = await _make_retrying_call(
                provider, model_name, messages, temperature, max_tokens, run_id,
            )
            logger.info(
                "LLM OK | agent=%s provider=%s model=%s tokens=%s latency=%sms run_id=%s",
                agent.value, provider, result["model_used"],
                result["total_tokens"], result["latency_ms"], run_id,
            )
            return result
        except DailyQuotaExhausted:
            # OpenRouter daily limit — try next model (possibly different provider)
            logger.warning(
                "OpenRouter daily quota hit — trying next model | agent=%s model=%s",
                agent.value, prefixed_model,
            )
            last_err = RuntimeError("OpenRouter daily quota exhausted")
            continue
        except Exception as err:
            last_err = err
            if i < len(models) - 1:
                logger.warning(
                    "LLM model %d/%d failed — trying next | agent=%s provider=%s model=%s error=%s",
                    i + 1, len(models), agent.value, provider, prefixed_model, err,
                )
            else:
                logger.error(
                    "LLM FAILED (all %d models) | agent=%s last_model=%s error=%s",
                    len(models), agent.value, prefixed_model, err,
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
    "TAVILY_API_KEY",
    "LANGCHAIN_API_KEY",
]

_LLM_KEY_VARS: list[str] = [
    "OPENROUTER_API_KEY",
    "GEMINI_API_KEY",
    "GROQ_API_KEY",
]


def validate_environment() -> None:
    """Fail-fast on startup if any required env var is missing."""
    missing = [k for k in REQUIRED_ENV_VARS if not os.getenv(k)]
    if missing:
        raise EnvironmentError(
            f"Missing required environment variables: {', '.join(missing)}. "
            "Check your .env file."
        )

    # At least one LLM provider key must be set
    has_llm_key = any(os.getenv(k) for k in _LLM_KEY_VARS)
    if not has_llm_key:
        raise EnvironmentError(
            "No LLM provider API key found. Set at least one of: "
            f"{', '.join(_LLM_KEY_VARS)} in your .env file."
        )

    configured = [k for k in _LLM_KEY_VARS if os.getenv(k)]
    logger.info("Environment validated — LLM providers: %s", ', '.join(configured))


# ─────────────────────────────────────────────
# 9. Settings — immutable single source of truth
# ─────────────────────────────────────────────
@dataclass(frozen=True)
class Settings:
    # API keys
    openrouter_api_key: str   = field(default_factory=lambda: os.getenv("OPENROUTER_API_KEY", ""))
    gemini_api_key:     str   = field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))
    groq_api_key:       str   = field(default_factory=lambda: os.getenv("GROQ_API_KEY", ""))
    tavily_api_key:     str   = field(default_factory=lambda: os.getenv("TAVILY_API_KEY", ""))
    firecrawl_api_key:  str   = field(default_factory=lambda: os.getenv("FIRECRAWL_API_KEY", ""))
    langchain_api_key:  str   = field(default_factory=lambda: os.getenv("LANGCHAIN_API_KEY", ""))

    # Database
    database_url:       str   = field(default_factory=lambda: os.getenv("DATABASE_URL", "postgresql+asyncpg://localhost:5432/agentic"))
    redis_url:          str   = field(default_factory=lambda: os.getenv("REDIS_URL", "redis://localhost:6379"))

    # Docker sandbox hard limits
    sandbox_memory_mb:  int   = 1024
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