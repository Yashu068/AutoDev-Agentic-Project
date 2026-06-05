"""
agents/research_agent.py
------------------------
Agent 1 — Research

Job:
    User ka PRD text leke web se information gather karta hai.
    Output: structured research_output JSON jo Planner padhega.

Tools used:
    1. Tavily      — web search (primary)
    2. Firecrawl   — URL scraping / documentation reading (primary)
    3. BeautifulSoup — fallback scraper agar Firecrawl fail ho

Output shape (research_output):
    {
        "summary":          str,         # kya banana hai — 2-3 lines
        "tech_stack":       List[str],   # ["FastAPI", "PostgreSQL", ...]
        "references":       List[{       # useful URLs
                                "url":     str,
                                "title":   str,
                                "snippet": str
                            }],
        "similar_projects": List[str],   # similar open-source projects
        "key_concepts":     List[str],   # important concepts to keep in mind
    }
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import httpx
from bs4 import BeautifulSoup
from firecrawl import FirecrawlApp
from tavily import TavilyClient

from config import AgentName, build_messages, call_llm, settings
from graph.state import AutoDevState, RunStatus, log

logger = logging.getLogger("agentic-platform")


# ─────────────────────────────────────────────────────────────────────────────
# 1. Tool clients (lazy singletons)
# ─────────────────────────────────────────────────────────────────────────────

_tavily: TavilyClient | None = None
_firecrawl: FirecrawlApp | None = None


def _get_tavily() -> TavilyClient:
    global _tavily
    if _tavily is None:
        _tavily = TavilyClient(api_key=settings.tavily_api_key)
    return _tavily


def _get_firecrawl() -> FirecrawlApp:
    global _firecrawl
    if _firecrawl is None:
        _firecrawl = FirecrawlApp(api_key=settings.firecrawl_api_key)
    return _firecrawl


# ─────────────────────────────────────────────────────────────────────────────
# 2. Tool functions (synchronous — called via asyncio.to_thread in run())
# ─────────────────────────────────────────────────────────────────────────────

def tavily_search(query: str, max_results: int = 5) -> list[dict[str, str]]:
    """
    Tavily se web search karo.
    Returns list of {url, title, snippet}.
    """
    try:
        response = _get_tavily().search(
            query=query,
            max_results=max_results,
            search_depth="advanced",        # deeper results
            include_answer=False,
            include_raw_content=False,
        )
        results = []
        for r in response.get("results", []):
            results.append({
                "url":     r.get("url", ""),
                "title":   r.get("title", ""),
                "snippet": r.get("content", "")[:500],   # trim long snippets
            })
        logger.info("Tavily search OK | query='%s' results=%d", query, len(results))
        return results

    except Exception as e:
        logger.warning("Tavily search FAILED | query='%s' error=%s", query, e)
        return []


def firecrawl_scrape(url: str) -> str:
    """
    Firecrawl se ek URL ko clean markdown mein convert karo.
    Returns scraped text or empty string on failure.
    """
    try:
        result = _get_firecrawl().scrape_url(
            url,
            params={"formats": ["markdown"]},
        )
        content = result.get("markdown", "") or ""
        logger.info("Firecrawl scrape OK | url=%s chars=%d", url, len(content))
        return content[:3000]   # token limit ke liye trim

    except Exception as e:
        logger.warning("Firecrawl scrape FAILED | url=%s error=%s — trying BS4", url, e)
        return _bs4_scrape(url)


def _bs4_scrape(url: str) -> str:
    """
    BeautifulSoup fallback scraper.
    Firecrawl fail hone pe yahi use hota hai.
    """
    try:
        resp = httpx.get(url, timeout=10, follow_redirects=True)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        # Remove noise
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()

        text = soup.get_text(separator="\n", strip=True)
        # Collapse blank lines
        lines = [l for l in text.splitlines() if l.strip()]
        clean = "\n".join(lines)
        logger.info("BS4 scrape OK | url=%s chars=%d", url, len(clean))
        return clean[:3000]

    except Exception as e:
        logger.warning("BS4 scrape FAILED | url=%s error=%s", url, e)
        return ""


# ─────────────────────────────────────────────────────────────────────────────
# 3. LLM prompts
# ─────────────────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """
You are a senior software architect and research specialist.
Your job is to analyze a product requirement and gather structured technical research.

You will be given:
- The user's PRD (Product Requirements Document) in plain English
- Web search results and scraped documentation

Your output MUST be valid JSON only — no explanation, no markdown, no extra text.
Respond with EXACTLY this structure:
{
    "summary": "2-3 line summary of what needs to be built",
    "tech_stack": ["technology1", "technology2"],
    "references": [
        {"url": "https://...", "title": "...", "snippet": "..."}
    ],
    "similar_projects": ["project1", "project2"],
    "key_concepts": ["concept1", "concept2"]
}
""".strip()


_QUERY_EXTRACTION_SYSTEM = """You extract concise web search queries from a product requirement.
Return ONLY a JSON array of 2-3 short search queries. No explanation, no markdown fences.
Example: ["FastAPI REST API authentication tutorial", "PostgreSQL async SQLAlchemy"]""".strip()


def _build_user_prompt(
    prd_text: str,
    search_results: list[dict],
    scraped_docs: list[str],
) -> str:
    """Assemble the user prompt with PRD + search context."""

    search_block = json.dumps(search_results, indent=2) if search_results else "No results found."
    docs_block   = "\n\n---\n\n".join(scraped_docs) if scraped_docs else "No documentation scraped."

    return f"""
## User Requirement (PRD)
{prd_text.strip()}

## Web Search Results
{search_block}

## Scraped Documentation (top URLs)
{docs_block}

Now produce the JSON research output.
""".strip()


# ─────────────────────────────────────────────────────────────────────────────
# 4. Parse + validate LLM output
# ─────────────────────────────────────────────────────────────────────────────

def _parse_research_output(raw: str) -> dict[str, Any]:
    """
    LLM response ko parse karo.
    Agar JSON invalid ho to safe fallback dict return karo.
    """
    # Strip markdown fences if LLM added them
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        cleaned = "\n".join(lines[1:-1]) if len(lines) > 2 else cleaned

    try:
        data = json.loads(cleaned)
        # Basic shape validation
        assert isinstance(data.get("summary"), str)
        assert isinstance(data.get("tech_stack"), list)
        assert isinstance(data.get("references"), list)
        assert isinstance(data.get("similar_projects"), list)
        assert isinstance(data.get("key_concepts"), list)
        return data

    except Exception as e:
        logger.error("Research output parse FAILED | error=%s | raw=%s", e, raw[:200])
        # Safe fallback — pipeline wont crash
        return {
            "summary":          raw[:500],
            "tech_stack":       [],
            "references":       [],
            "similar_projects": [],
            "key_concepts":     [],
        }


def _extract_queries_from_prd(prd_text: str, run_id: str) -> tuple[list[str], int]:
    """
    Use a lightweight LLM call to extract clean search queries from the PRD
    instead of blindly slicing the raw text.
    Falls back to simple slicing if the LLM call fails.
    Returns (queries, tokens_used).
    """
    try:
        result = call_llm(
            agent=AgentName.RESEARCH,
            messages=build_messages(
                _QUERY_EXTRACTION_SYSTEM,
                f"Extract search queries from this PRD:\n\n{prd_text[:1000]}",
            ),
            temperature=0.0,
            max_tokens=256,
            run_id=run_id,
        )
        tokens = int(result.get("total_tokens", 0))
        raw = str(result["content"]).strip()
        # Strip markdown fences if present
        if raw.startswith("```"):
            lines = raw.splitlines()
            raw = "\n".join(lines[1:-1]) if len(lines) > 2 else raw
        queries = json.loads(raw)
        if isinstance(queries, list) and len(queries) >= 1:
            return [str(q) for q in queries[:3]], tokens
    except Exception as e:
        logger.warning("Query extraction failed, using fallback | error=%s", e)

    # Fallback: take first sentence-like chunk
    first_line = prd_text.strip().split("\n")[0][:150]
    return [first_line, f"how to build {first_line[:80]}"], 0


# ─────────────────────────────────────────────────────────────────────────────
# 5. Main agent entry point
# ─────────────────────────────────────────────────────────────────────────────

async def run(state: AutoDevState) -> AutoDevState:
    """
    Research agent ka main function.
    Orchestrator is function ko call karta hai.

    Steps:
        1. PRD se search queries banao (via LLM)
        2. Tavily se web search karo (non-blocking)
        3. Top 2 URLs ko Firecrawl/BS4 se scrape karo (non-blocking)
        4. LLM ko sab deke structured JSON lo
        5. research_output state mein save karo
    """
    log(state, "Research", "Agent started")
    prd = state["prd_text"]
    run_id = state["run_id"]

    # ── Step 1: Extract search queries via LLM ────────────────────────────────
    queries, extraction_tokens = _extract_queries_from_prd(prd, run_id)
    state["total_tokens"] = state.get("total_tokens", 0) + extraction_tokens
    log(state, "Research", f"Running {len(queries)} Tavily searches: {queries}")

    # ── Step 2: Tavily web search (non-blocking) ──────────────────────────────
    all_results: list[dict] = []
    for q in queries:
        results = await asyncio.to_thread(tavily_search, q, 5)
        all_results.extend(results)

    # Deduplicate by URL
    seen_urls: set[str] = set()
    unique_results: list[dict] = []
    for r in all_results:
        if r["url"] not in seen_urls:
            seen_urls.add(r["url"])
            unique_results.append(r)

    log(state, "Research", f"Tavily returned {len(unique_results)} unique results")

    # ── Step 3: Scrape top 2 URLs (non-blocking) ──────────────────────────────
    scraped_docs: list[str] = []
    top_urls = [r["url"] for r in unique_results[:2]]   # only top 2 — token budget

    for url in top_urls:
        log(state, "Research", f"Scraping: {url}")
        content = await asyncio.to_thread(firecrawl_scrape, url)
        if content:
            scraped_docs.append(f"Source: {url}\n\n{content}")

    log(state, "Research", f"Scraped {len(scraped_docs)} documents")

    # ── Step 4: LLM call ──────────────────────────────────────────────────────
    user_prompt = _build_user_prompt(prd, unique_results[:8], scraped_docs)
    messages    = build_messages(_SYSTEM_PROMPT, user_prompt)

    log(state, "Research", "Calling LLM for structured research output")
    try:
        llm_result = call_llm(
            agent=AgentName.RESEARCH,
            messages=messages,
            temperature=0.1,        # low temp = more deterministic JSON
            max_tokens=2048,
            run_id=run_id,
        )
    except RuntimeError as e:
        log(state, "Research", f"LLM call failed: {e}")
        state["status"] = RunStatus.FAILED
        return state

    # ── Step 5: Parse + save ──────────────────────────────────────────────────
    research_output = _parse_research_output(str(llm_result["content"]))

    # Token tracking (cast to int — call_llm returns dict[str, object])
    state["total_tokens"] = state.get("total_tokens", 0) + int(llm_result["total_tokens"])

    # Save to state
    state["research_output"] = research_output

    log(
        state,
        "Research",
        f"Done | tech_stack={research_output['tech_stack']} "
        f"references={len(research_output['references'])} "
        f"tokens={llm_result['total_tokens']}",
    )

    return state