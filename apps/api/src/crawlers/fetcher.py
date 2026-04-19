"""URL fetcher — supports static HTTP and JS-rendered pages via Playwright."""

import asyncio
from dataclasses import dataclass
from enum import StrEnum

import httpx
from playwright.async_api import async_playwright

import structlog

logger = structlog.get_logger()


class FetchMode(StrEnum):
    """How to fetch a page."""
    STATIC = "static"
    BROWSER = "browser"


@dataclass
class FetchResult:
    """Result of fetching a single URL."""
    url: str
    html: str
    status_code: int
    fetch_mode: FetchMode
    error: str | None = None


async def fetch_static(url: str, timeout: float = 30.0) -> FetchResult:
    """Fetch a URL using httpx (no JS rendering)."""
    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=timeout,
            headers={"User-Agent": "RAG-Pipeline-Bot/1.0"},
        ) as client:
            response = await client.get(url)
            return FetchResult(
                url=url,
                html=response.text,
                status_code=response.status_code,
                fetch_mode=FetchMode.STATIC,
            )
    except Exception as e:
        logger.error("static_fetch_failed", url=url, error=str(e))
        return FetchResult(
            url=url, html="", status_code=0,
            fetch_mode=FetchMode.STATIC, error=str(e),
        )


async def fetch_with_browser(url: str, timeout: float = 60000) -> FetchResult:
    """Fetch a URL using Playwright headless Chromium (handles JS-rendered pages)."""
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, wait_until="networkidle", timeout=timeout)
            html = await page.content()
            await browser.close()
            return FetchResult(
                url=url, html=html, status_code=200,
                fetch_mode=FetchMode.BROWSER,
            )
    except Exception as e:
        logger.error("browser_fetch_failed", url=url, error=str(e))
        return FetchResult(
            url=url, html="", status_code=0,
            fetch_mode=FetchMode.BROWSER, error=str(e),
        )


async def fetch_url(url: str, use_browser: bool = False) -> FetchResult:
    """Fetch a URL — try static first, fall back to browser if needed."""
    if use_browser:
        return await fetch_with_browser(url)

    result = await fetch_static(url)
    # If static fetch got very little content, try browser
    if result.status_code == 200 and len(result.html) < 500:
        logger.info("static_fetch_too_small_falling_back_to_browser", url=url)
        return await fetch_with_browser(url)

    return result
