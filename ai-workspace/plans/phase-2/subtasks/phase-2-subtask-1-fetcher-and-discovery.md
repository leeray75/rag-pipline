# Phase 2, Subtask 1 — Dependencies + URL Fetcher + Link Discovery

> **Phase**: Phase 2 — Crawl & Convert
> **Prerequisites**: Phase 1 complete (Docker Compose running, FastAPI skeleton serving `/api/v1/health`, Postgres schemas migrated, Next.js scaffold loading)
> **Scope**: 3 files to create, 1 file to modify

---

## Relevant Technology Stack

| Package | Pinned Version | Purpose |
|---|---|---|
| Python | 3.13.x | Runtime |
| httpx | ≥0.28.0 | Static HTTP fetching |
| Playwright | 1.58.0 | JS-rendered page fetching |
| BeautifulSoup4 | 4.14.3 | HTML parsing for link extraction |
| markitdown | 0.1.5 | HTML→Markdown (dep added now, used in Subtask 2) |
| trafilatura | ≥2.0.0 | Content extraction |
| langchain-anthropic | ≥0.4.0 | Claude LLM fallback for link discovery |
| langchain-core | ≥0.3.0 | LangChain base |
| structlog | 25.4.0 | Structured logging |

---

## Step 1: Add Phase 2 Python Dependencies

**Working directory**: `rag-pipeline/apps/api/`

### 1.1 Update `pyproject.toml` — add to `[project.dependencies]`

Add these lines to the existing dependencies list:

```toml
    "markitdown>=0.1.5",
    "beautifulsoup4>=4.14.0",
    "playwright>=1.58.0",
    "trafilatura>=2.0.0",
    "httpx>=0.28.0",
    "langchain-anthropic>=0.4.0",
    "langchain-core>=0.3.0",
```

### 1.2 Install Playwright browsers

After pip install, run:

```bash
playwright install chromium
```

**Verify**: `python -c "import markitdown, bs4, playwright"` succeeds.

---

## Step 2: Build the URL Fetcher Service

**Working directory**: `rag-pipeline/apps/api/src/crawlers/`

### 2.1 Create `fetcher.py`

```python
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
```

---

## Step 3: Build the Link Discovery Service

**Working directory**: `rag-pipeline/apps/api/src/crawlers/`

### 3.1 Create `link_discovery.py`

```python
"""Discover documentation links from a seed URL using BS4 + LLM fallback."""

import json
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

import structlog

logger = structlog.get_logger()


@dataclass
class DiscoveredLink:
    """A discovered documentation page link."""
    href: str
    title: str
    source: str  # "css_selector" or "llm_extraction"


def extract_links_with_selectors(
    html: str,
    base_url: str,
    nav_selectors: list[str] | None = None,
) -> list[DiscoveredLink]:
    """Extract documentation links using CSS selectors on nav/sidebar elements."""
    if nav_selectors is None:
        nav_selectors = [
            "nav a",
            "[class*='sidebar'] a",
            "[class*='nav'] a",
            "[class*='menu'] a",
            "[class*='toc'] a",
            "[role='navigation'] a",
            "aside a",
        ]

    soup = BeautifulSoup(html, "html.parser")
    parsed_base = urlparse(base_url)
    seen_urls: set[str] = set()
    links: list[DiscoveredLink] = []

    for selector in nav_selectors:
        for anchor in soup.select(selector):
            href = anchor.get("href")
            if not href or href.startswith("#") or href.startswith("javascript:"):
                continue

            absolute_url = urljoin(base_url, href)
            parsed = urlparse(absolute_url)

            # Filter: same origin only
            if parsed.netloc != parsed_base.netloc:
                continue

            # Deduplicate
            clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
            if clean_url in seen_urls:
                continue
            seen_urls.add(clean_url)

            title = anchor.get_text(strip=True) or parsed.path.split("/")[-1]
            links.append(DiscoveredLink(
                href=clean_url, title=title, source="css_selector",
            ))

    logger.info("css_links_extracted", count=len(links), base_url=base_url)
    return links


async def extract_links_with_llm(
    html: str,
    base_url: str,
) -> list[DiscoveredLink]:
    """Use Claude to extract doc links when CSS selectors fail or find too few.

    IMPORTANT: Requires ANTHROPIC_API_KEY environment variable.
    """
    from langchain_anthropic import ChatAnthropic

    # Trim HTML to nav-relevant sections to save tokens
    soup = BeautifulSoup(html, "html.parser")
    nav_sections = []
    for tag in soup.find_all(["nav", "aside", "header"]):
        nav_sections.append(str(tag)[:5000])

    nav_html = "\n---\n".join(nav_sections) if nav_sections else html[:10000]

    llm = ChatAnthropic(model="claude-sonnet-4-20250514", max_tokens=4096, temperature=0)

    prompt = f"""Extract all documentation page links from this HTML navigation.
The base URL is: {base_url}

Return ONLY a JSON array of objects with "href" and "title" keys.
Only include links that are part of the same documentation site.
Do not include external links, social media, or non-documentation pages.

HTML:
{nav_html}

JSON array:"""

    response = await llm.ainvoke(prompt)
    content = response.content

    try:
        # Parse JSON from response
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        raw_links = json.loads(content.strip())
        links = []
        for item in raw_links:
            href = urljoin(base_url, item.get("href", ""))
            title = item.get("title", "")
            links.append(DiscoveredLink(href=href, title=title, source="llm_extraction"))

        logger.info("llm_links_extracted", count=len(links), base_url=base_url)
        return links
    except (json.JSONDecodeError, KeyError) as e:
        logger.error("llm_link_extraction_failed", error=str(e))
        return []


async def discover_doc_links(
    html: str,
    base_url: str,
    min_links_threshold: int = 3,
) -> list[DiscoveredLink]:
    """Discover documentation links. Uses CSS selectors first, LLM fallback if too few found."""
    links = extract_links_with_selectors(html, base_url)

    if len(links) < min_links_threshold:
        logger.info("too_few_css_links_trying_llm", css_count=len(links))
        llm_links = await extract_links_with_llm(html, base_url)
        # Merge, preferring CSS-extracted links
        seen = {link.href for link in links}
        for link in llm_links:
            if link.href not in seen:
                links.append(link)
                seen.add(link.href)

    return links
```

---

## Files to Create/Modify

| Action | File Path |
|---|---|
| **Modify** | `rag-pipeline/apps/api/pyproject.toml` |
| **Create** | `rag-pipeline/apps/api/src/crawlers/__init__.py` (if not exists) |
| **Create** | `rag-pipeline/apps/api/src/crawlers/fetcher.py` |
| **Create** | `rag-pipeline/apps/api/src/crawlers/link_discovery.py` |

---

## Done-When Checklist

- [ ] `python -c "import markitdown, bs4, playwright"` succeeds inside the API container
- [ ] `playwright install chromium` completes without errors
- [ ] `rag-pipeline/apps/api/src/crawlers/fetcher.py` exists and exports `fetch_url`, `fetch_static`, `fetch_with_browser`, `FetchResult`, `FetchMode`
- [ ] `rag-pipeline/apps/api/src/crawlers/link_discovery.py` exists and exports `discover_doc_links`, `extract_links_with_selectors`, `extract_links_with_llm`, `DiscoveredLink`
- [ ] A simple test script can fetch `https://example.com` and return HTML content
- [ ] Calling `discover_doc_links(html, url)` returns a list of `DiscoveredLink` objects from any doc site HTML

---

## Summary Report

Upon completion of this subtask, create a summary report at:
`rag-pipeline/ai-workspace/summary-reports/phase-2-subtask-1-fetcher-and-discovery-summary.md`

The summary report must include:
- **Subtask**: Phase 2, Subtask 1 — Dependencies + URL Fetcher + Link Discovery
- **Status**: Complete / Partial / Blocked
- **Date**: {ISO 8601 date}
- **Files Created/Modified**: List every file path
- **Key Decisions**: Any deviations from the plan and why
- **Issues Encountered**: Problems and resolutions
- **Dependencies for Next Subtask**: What the next subtask needs to know
- **Verification Results**: Output of Done-When checklist items
