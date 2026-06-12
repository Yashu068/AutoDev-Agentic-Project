"""
tools/smart_scraper.py — Web Search + URL Scraping
====================================================
Research agent ka helper — web search (Tavily) aur
URL scraping (Firecrawl → BeautifulSoup fallback).

Usage:
    from tools.smart_scraper import web_search, scrape_url, scrape_urls

    # Search the web
    results = web_search("FastAPI authentication tutorial")
    # [{"url": "...", "title": "...", "snippet": "..."}]

    # Scrape a single URL
    text = scrape_url("https://docs.python.org/3/tutorial/")

    # Scrape multiple URLs concurrently
    docs = await scrape_urls(["https://...", "https://..."])
"""

from __future__ import annotations

import asyncio
import logging

import httpx
from bs4 import BeautifulSoup

from config import settings

logger = logging.getLogger("agentic-platform")

# Trim scraped content to stay within token budget
_MAX_SCRAPE_CHARS = 3000
_MAX_SNIPPET_CHARS = 500


# ─────────────────────────────────────────────────────────────────────────────
# 1. Lazy client singletons
# ─────────────────────────────────────────────────────────────────────────────

_tavily = None
_firecrawl = None


def _get_tavily():
    global _tavily
    if _tavily is None:
        from tavily import TavilyClient
        _tavily = TavilyClient(api_key=settings.tavily_api_key)
    return _tavily


def _get_firecrawl():
    global _firecrawl
    if _firecrawl is None:
        from firecrawl import FirecrawlApp
        _firecrawl = FirecrawlApp(api_key=settings.firecrawl_api_key)
    return _firecrawl


# ─────────────────────────────────────────────────────────────────────────────
# 2. Web Search (Tavily)
# ─────────────────────────────────────────────────────────────────────────────

def web_search(query: str, max_results: int = 5) -> list[dict[str, str]]:
    """
    Tavily se web search karta hai.

    Parameters
    ----------
    query : str
        Search query string.
    max_results : int
        Maximum number of results to return.

    Returns
    -------
    List of {"url": str, "title": str, "snippet": str}
    """
    try:
        response = _get_tavily().search(
            query=query,
            max_results=max_results,
            search_depth="advanced",
            include_answer=False,
            include_raw_content=False,
        )
        results = []
        for r in response.get("results", []):
            results.append({
                "url":     r.get("url", ""),
                "title":   r.get("title", ""),
                "snippet": r.get("content", "")[:_MAX_SNIPPET_CHARS],
            })
        logger.info("Tavily search OK | query='%s' results=%d", query, len(results))
        return results

    except Exception as e:
        logger.warning("Tavily search FAILED | query='%s' error=%s", query, e)
        return []


# ─────────────────────────────────────────────────────────────────────────────
# 3. URL Scraping — Firecrawl (primary) → BeautifulSoup (fallback)
# ─────────────────────────────────────────────────────────────────────────────

def scrape_url(url: str) -> str:
    """
    Ek URL se clean text nikalta hai.
    Pehle Firecrawl try karta hai, fail hone pe BS4 fallback.

    Parameters
    ----------
    url : str
        The URL to scrape.

    Returns
    -------
    Cleaned text content (trimmed to ~3000 chars), or empty string on failure.
    """
    # Try Firecrawl first
    content = _firecrawl_scrape(url)
    if content:
        return content

    # Fallback to BeautifulSoup
    return _bs4_scrape(url)


async def scrape_urls(urls: list[str]) -> list[dict[str, str]]:
    """
    Multiple URLs ko concurrently scrape karta hai.

    Parameters
    ----------
    urls : list[str]
        List of URLs to scrape.

    Returns
    -------
    List of {"url": str, "content": str} for each successfully scraped URL.
    """
    async def _scrape_one(url: str) -> dict[str, str]:
        content = await asyncio.to_thread(scrape_url, url)
        return {"url": url, "content": content}

    tasks = [_scrape_one(u) for u in urls]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    docs = []
    for r in results:
        if isinstance(r, dict) and r.get("content"):
            docs.append(r)
        elif isinstance(r, Exception):
            logger.warning("Scrape task failed: %s", r)

    logger.info("Scraped %d/%d URLs successfully", len(docs), len(urls))
    return docs


# ─────────────────────────────────────────────────────────────────────────────
# 4. Internal scrapers
# ─────────────────────────────────────────────────────────────────────────────

def _firecrawl_scrape(url: str) -> str:
    """Firecrawl se URL ko clean markdown mein convert karo."""
    try:
        result = _get_firecrawl().scrape_url(
            url,
            params={"formats": ["markdown"]},
        )
        content = result.get("markdown", "") or ""
        logger.info("Firecrawl scrape OK | url=%s chars=%d", url, len(content))
        return content[:_MAX_SCRAPE_CHARS]

    except Exception as e:
        logger.warning("Firecrawl scrape FAILED | url=%s error=%s", url, e)
        return ""


def _bs4_scrape(url: str) -> str:
    """BeautifulSoup fallback scraper — Firecrawl fail hone pe use hota hai."""
    try:
        resp = httpx.get(url, timeout=10, follow_redirects=True)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        # Remove noise elements
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()

        text = soup.get_text(separator="\n", strip=True)
        lines = [line for line in text.splitlines() if line.strip()]
        clean = "\n".join(lines)

        logger.info("BS4 scrape OK | url=%s chars=%d", url, len(clean))
        return clean[:_MAX_SCRAPE_CHARS]

    except Exception as e:
        logger.warning("BS4 scrape FAILED | url=%s error=%s", url, e)
        return ""
