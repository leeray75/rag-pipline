# Phase 2 — URL Ingestion, Crawling & HTML→Markdown Conversion

> **Prerequisites**: Phase 1 complete — Docker Compose running, FastAPI skeleton serving `/api/v1/health`, Postgres schemas migrated, Next.js scaffold loading.
> **Ref**: [phase-0-index.md](phase-0-index.md) for pinned versions.

---

## Objective

Build the full URL intake → HTML fetch → doc discovery → Markdown conversion pipeline. Create the Celery task chain, WebSocket progress streaming, and a staging file browser UI in the dashboard.

---

## Task 1: Add Phase 2 Python Dependencies

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

**Done when**: `python -c "import markitdown, bs4, playwright"` succeeds.

---

## Task 2: Build the URL Fetcher Service

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

**Done when**: A simple test script can fetch `https://example.com` and return HTML content.

---

## Task 3: Build the Link Discovery Service

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

**Done when**: Calling `discover_doc_links(html, url)` returns a list of `DiscoveredLink` objects from any doc site HTML.

---

## Task 4: Build the Markdown Converter Service

**Working directory**: `rag-pipeline/apps/api/src/converters/`

### 4.1 Create `markdown_converter.py`

```python
"""HTML to Markdown conversion using markitdown with pre/post processing."""

import re
from dataclasses import dataclass
from datetime import datetime, timezone

from markitdown import MarkItDown

import structlog

logger = structlog.get_logger()


@dataclass
class ConversionResult:
    """Result of converting HTML to Markdown."""
    markdown: str
    title: str
    word_count: int
    source_url: str
    error: str | None = None


def _sanitize_html(html: str) -> str:
    """Remove noise elements before conversion."""
    # Remove script and style tags
    html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)
    # Remove common noise elements
    html = re.sub(r"<(nav|footer|header)[^>]*>.*?</\1>", "", html, flags=re.DOTALL | re.IGNORECASE)
    # Remove cookie banners
    html = re.sub(r'<div[^>]*class="[^"]*cookie[^"]*"[^>]*>.*?</div>', "", html, flags=re.DOTALL | re.IGNORECASE)
    return html


def _extract_title(html: str) -> str:
    """Extract title from HTML."""
    # Try <title> tag
    match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1).strip()
    # Try first <h1>
    match = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.IGNORECASE | re.DOTALL)
    if match:
        # Strip HTML tags from h1 content
        return re.sub(r"<[^>]+>", "", match.group(1)).strip()
    return "Untitled"


def _add_frontmatter(markdown: str, title: str, source_url: str, description: str = "") -> str:
    """Prepend YAML frontmatter to the Markdown content."""
    now = datetime.now(timezone.utc).isoformat()
    frontmatter = f"""---
title: "{title}"
description: "{description}"
source_url: "{source_url}"
fetched_at: "{now}"
tags: []
---

"""
    return frontmatter + markdown


def _post_process_markdown(markdown: str) -> str:
    """Clean up common markitdown artifacts."""
    # Remove excessive blank lines (more than 2 consecutive)
    markdown = re.sub(r"\n{4,}", "\n\n\n", markdown)
    # Fix code blocks without language identifier
    markdown = re.sub(r"```\n", "```text\n", markdown)
    # Remove residual HTML tags
    markdown = re.sub(r"</?(?:div|span|section|article)[^>]*>", "", markdown)
    return markdown.strip()


def convert_html_to_markdown(html: str, source_url: str) -> ConversionResult:
    """Convert HTML to clean Markdown with frontmatter."""
    try:
        title = _extract_title(html)
        sanitized = _sanitize_html(html)

        # Use markitdown for conversion
        converter = MarkItDown()
        result = converter.convert_html(sanitized)
        markdown = result.text_content

        # Post-process
        markdown = _post_process_markdown(markdown)

        # Generate description from first 200 chars
        desc_text = re.sub(r"[#*\[\]`]", "", markdown[:300]).strip()
        description = desc_text[:200] if len(desc_text) > 200 else desc_text

        # Add frontmatter
        markdown = _add_frontmatter(markdown, title, source_url, description)

        word_count = len(markdown.split())

        logger.info("html_converted", url=source_url, words=word_count)
        return ConversionResult(
            markdown=markdown,
            title=title,
            word_count=word_count,
            source_url=source_url,
        )
    except Exception as e:
        logger.error("conversion_failed", url=source_url, error=str(e))
        return ConversionResult(
            markdown="", title="", word_count=0,
            source_url=source_url, error=str(e),
        )
```

**Done when**: `convert_html_to_markdown("<html><body><h1>Test</h1><p>Hello</p></body></html>", "https://example.com")` returns valid Markdown with frontmatter.

---

## Task 5: Build Celery Task Chain

**Working directory**: `rag-pipeline/apps/api/src/workers/`

### 5.1 Create `crawl_tasks.py`

```python
"""Celery tasks for URL crawling and document conversion."""

import asyncio
import json
import uuid
from pathlib import Path

from celery import chain, chord, group

from src.workers.celery_app import celery_app
from src.crawlers.fetcher import fetch_url, FetchResult
from src.crawlers.link_discovery import discover_doc_links
from src.converters.markdown_converter import convert_html_to_markdown

import structlog

logger = structlog.get_logger()

STAGING_DIR = Path("/app/data/staging")


def _ensure_job_dir(job_id: str) -> Path:
    """Create and return the staging directory for a job."""
    job_dir = STAGING_DIR / job_id
    (job_dir / "html").mkdir(parents=True, exist_ok=True)
    (job_dir / "markdown").mkdir(parents=True, exist_ok=True)
    return job_dir


@celery_app.task(bind=True, name="crawl.fetch_seed_url")
def fetch_seed_url(self, job_id: str, url: str, use_browser: bool = False):
    """Fetch the seed URL HTML. Returns serialized FetchResult."""
    result = asyncio.run(fetch_url(url, use_browser=use_browser))

    # Save raw HTML to staging
    job_dir = _ensure_job_dir(job_id)
    html_path = job_dir / "html" / "seed.html"
    html_path.write_text(result.html, encoding="utf-8")

    return {
        "job_id": job_id,
        "url": result.url,
        "html_path": str(html_path),
        "status_code": result.status_code,
        "fetch_mode": result.fetch_mode,
        "error": result.error,
    }


@celery_app.task(bind=True, name="crawl.discover_links")
def discover_links(self, seed_result: dict, crawl_all: bool = True):
    """Discover documentation page links from the seed URL."""
    if not crawl_all:
        # Single page mode — just return the seed URL
        return {
            "job_id": seed_result["job_id"],
            "links": [{"href": seed_result["url"], "title": "Seed Page", "source": "direct"}],
        }

    html = Path(seed_result["html_path"]).read_text(encoding="utf-8")
    links = asyncio.run(discover_doc_links(html, seed_result["url"]))

    # Always include the seed URL
    seed_in_list = any(link.href == seed_result["url"] for link in links)
    link_dicts = [{"href": l.href, "title": l.title, "source": l.source} for l in links]
    if not seed_in_list:
        link_dicts.insert(0, {"href": seed_result["url"], "title": "Seed Page", "source": "direct"})

    logger.info("links_discovered", job_id=seed_result["job_id"], count=len(link_dicts))
    return {"job_id": seed_result["job_id"], "links": link_dicts}


@celery_app.task(bind=True, name="crawl.fetch_and_convert_page", rate_limit="1/s")
def fetch_and_convert_page(self, job_id: str, link: dict, doc_index: int):
    """Fetch a single page, convert to Markdown, and save to staging."""
    url = link["href"]
    title = link.get("title", "")

    # Fetch
    result = asyncio.run(fetch_url(url, use_browser=False))
    if result.error:
        return {
            "job_id": job_id,
            "doc_index": doc_index,
            "url": url,
            "status": "failed",
            "error": result.error,
        }

    job_dir = _ensure_job_dir(job_id)

    # Save raw HTML
    safe_name = f"doc_{doc_index:04d}"
    html_path = job_dir / "html" / f"{safe_name}.html"
    html_path.write_text(result.html, encoding="utf-8")

    # Convert to Markdown
    conversion = convert_html_to_markdown(result.html, url)
    if conversion.error:
        return {
            "job_id": job_id,
            "doc_index": doc_index,
            "url": url,
            "status": "conversion_failed",
            "error": conversion.error,
        }

    # Save Markdown
    md_path = job_dir / "markdown" / f"{safe_name}.md"
    md_path.write_text(conversion.markdown, encoding="utf-8")

    return {
        "job_id": job_id,
        "doc_index": doc_index,
        "url": url,
        "title": conversion.title,
        "word_count": conversion.word_count,
        "html_path": str(html_path),
        "markdown_path": str(md_path),
        "status": "converted",
    }


@celery_app.task(bind=True, name="crawl.finalize_crawl")
def finalize_crawl(self, results: list[dict], job_id: str):
    """Aggregate all fetch-and-convert results and update job status."""
    successful = [r for r in results if r.get("status") == "converted"]
    failed = [r for r in results if r.get("status") != "converted"]

    # Save manifest
    job_dir = _ensure_job_dir(job_id)
    manifest = {
        "job_id": job_id,
        "total_documents": len(results),
        "successful": len(successful),
        "failed": len(failed),
        "documents": results,
    }
    manifest_path = job_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    logger.info(
        "crawl_finalized",
        job_id=job_id,
        total=len(results),
        success=len(successful),
        failed=len(failed),
    )
    return manifest


def start_crawl_pipeline(job_id: str, url: str, crawl_all: bool = True):
    """Kick off the full crawl pipeline as a Celery workflow.

    Pipeline: fetch_seed → discover_links → fan-out fetch_and_convert → finalize
    """
    workflow = chain(
        fetch_seed_url.s(job_id, url, use_browser=False),
        discover_links.s(crawl_all=crawl_all),
        _fan_out_and_finalize.s(),
    )
    return workflow.apply_async()


@celery_app.task(bind=True, name="crawl.fan_out_and_finalize")
def _fan_out_and_finalize(self, discovery_result: dict):
    """Fan out fetch_and_convert tasks for all discovered links, then finalize."""
    job_id = discovery_result["job_id"]
    links = discovery_result["links"]

    # Create a group of fetch_and_convert tasks
    tasks = [
        fetch_and_convert_page.s(job_id, link, idx)
        for idx, link in enumerate(links)
    ]

    # Use chord: run all tasks in parallel, then call finalize
    callback = finalize_crawl.s(job_id=job_id)
    job = chord(tasks)(callback)
    return {"job_id": job_id, "task_count": len(tasks), "chord_id": str(job.id)}
```

**Done when**: `start_crawl_pipeline(job_id, url)` dispatches tasks to Celery and completes without errors.

---

## Task 6: Build API Router — Ingestion Jobs

**Working directory**: `rag-pipeline/apps/api/src/routers/`

### 6.1 Create `jobs.py`

```python
"""API routes for ingestion job management."""

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.models import Document, IngestionJob, JobStatus
from src.schemas import DocumentResponse, JobCreate, JobResponse, JobStatusResponse
from src.workers.crawl_tasks import start_crawl_pipeline

import structlog

logger = structlog.get_logger()

router = APIRouter()

STAGING_DIR = Path("/app/data/staging")


@router.post("/jobs", response_model=JobResponse, status_code=201)
async def create_job(payload: JobCreate, db: AsyncSession = Depends(get_db)):
    """Create a new ingestion job and start the crawl pipeline."""
    job = IngestionJob(
        url=str(payload.url),
        crawl_all_docs=payload.crawl_all_docs,
        status=JobStatus.PENDING,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    # Start Celery pipeline
    start_crawl_pipeline(
        job_id=str(job.id),
        url=str(payload.url),
        crawl_all=payload.crawl_all_docs,
    )

    # Update status to crawling
    job.status = JobStatus.CRAWLING
    await db.commit()
    await db.refresh(job)

    logger.info("job_created", job_id=str(job.id), url=str(payload.url))
    return job


@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(job_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get job details by ID."""
    result = await db.execute(select(IngestionJob).where(IngestionJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/jobs/{job_id}/status", response_model=JobStatusResponse)
async def get_job_status(job_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get lightweight job status for polling."""
    result = await db.execute(select(IngestionJob).where(IngestionJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/jobs/{job_id}/documents", response_model=list[DocumentResponse])
async def list_documents(job_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """List all documents for a job."""
    result = await db.execute(
        select(Document).where(Document.job_id == job_id).order_by(Document.created_at)
    )
    return result.scalars().all()


@router.get("/jobs/{job_id}/documents/{doc_id}")
async def get_document(job_id: uuid.UUID, doc_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get a single document with its raw HTML and Markdown content."""
    result = await db.execute(
        select(Document).where(Document.id == doc_id, Document.job_id == job_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    response = {
        "id": str(doc.id),
        "job_id": str(doc.job_id),
        "url": doc.url,
        "title": doc.title,
        "status": doc.status,
        "word_count": doc.word_count,
        "raw_html": None,
        "markdown": None,
    }

    # Read file contents if available
    if doc.raw_html_path:
        html_path = Path(doc.raw_html_path)
        if html_path.exists():
            response["raw_html"] = html_path.read_text(encoding="utf-8")

    if doc.markdown_path:
        md_path = Path(doc.markdown_path)
        if md_path.exists():
            response["markdown"] = md_path.read_text(encoding="utf-8")

    return response


@router.delete("/jobs/{job_id}/documents/{doc_id}", status_code=204)
async def delete_document(job_id: uuid.UUID, doc_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Remove a document from staging before audit."""
    result = await db.execute(
        select(Document).where(Document.id == doc_id, Document.job_id == job_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Delete files
    for path_str in [doc.raw_html_path, doc.markdown_path]:
        if path_str:
            p = Path(path_str)
            if p.exists():
                p.unlink()

    await db.delete(doc)
    await db.commit()
```

### 6.2 Create `websocket.py` — Real-time progress streaming

```python
"""WebSocket endpoint for real-time crawl progress streaming."""

import asyncio
import json
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

import structlog

logger = structlog.get_logger()

router = APIRouter()

# In-memory connection manager (for single-instance; use Redis PubSub for multi-instance)
class ConnectionManager:
    """Manage WebSocket connections per job."""

    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, job_id: str, websocket: WebSocket):
        await websocket.accept()
        if job_id not in self.active_connections:
            self.active_connections[job_id] = []
        self.active_connections[job_id].append(websocket)

    def disconnect(self, job_id: str, websocket: WebSocket):
        if job_id in self.active_connections:
            self.active_connections[job_id].remove(websocket)
            if not self.active_connections[job_id]:
                del self.active_connections[job_id]

    async def broadcast(self, job_id: str, message: dict):
        """Send a message to all connections for a job."""
        if job_id in self.active_connections:
            data = json.dumps(message)
            for connection in self.active_connections[job_id]:
                try:
                    await connection.send_text(data)
                except Exception:
                    pass


manager = ConnectionManager()


@router.websocket("/jobs/{job_id}/stream")
async def job_progress_stream(websocket: WebSocket, job_id: str):
    """WebSocket endpoint for streaming crawl progress events."""
    await manager.connect(job_id, websocket)
    try:
        while True:
            # Keep connection alive; client can send heartbeats
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        manager.disconnect(job_id, websocket)
```

### 6.3 Register routers in `src/main.py`

Add these imports and router registrations to the existing `main.py`:

```python
from src.routers import health, jobs, websocket

# After existing router registration, add:
app.include_router(jobs.router, prefix="/api/v1", tags=["jobs"])
app.include_router(websocket.router, prefix="/api/v1/ws", tags=["websocket"])
```

**Done when**: `POST /api/v1/jobs` with `{"url": "https://example.com", "crawl_all_docs": false}` returns 201 with a job object.

---

## Task 7: Build Staging File Browser UI

**Working directory**: `rag-pipeline/apps/web/`

### 7.1 Install additional UI dependencies

```bash
pnpm add @monaco-editor/react react-split-pane react-markdown remark-gfm
```

### 7.2 Create RTK Query endpoints — `src/store/api/jobs-api.ts`

```typescript
import { apiSlice } from "./api-slice";

export interface Job {
  id: string;
  url: string;
  status: string;
  crawl_all_docs: boolean;
  total_documents: number;
  processed_documents: number;
  current_audit_round: number;
  created_at: string;
  updated_at: string;
}

export interface DocumentItem {
  id: string;
  job_id: string;
  url: string;
  title: string | null;
  status: string;
  word_count: number | null;
  quality_score: number | null;
  created_at: string;
}

export interface DocumentDetail extends DocumentItem {
  raw_html: string | null;
  markdown: string | null;
}

export const jobsApi = apiSlice.injectEndpoints({
  endpoints: (builder) => ({
    createJob: builder.mutation<Job, { url: string; crawl_all_docs: boolean }>({
      query: (body) => ({ url: "/jobs", method: "POST", body }),
      invalidatesTags: ["Jobs"],
    }),
    getJob: builder.query<Job, string>({
      query: (id) => `/jobs/${id}`,
      providesTags: (result, error, id) => [{ type: "Jobs", id }],
    }),
    getJobStatus: builder.query<Job, string>({
      query: (id) => `/jobs/${id}/status`,
    }),
    listDocuments: builder.query<DocumentItem[], string>({
      query: (jobId) => `/jobs/${jobId}/documents`,
      providesTags: ["Documents"],
    }),
    getDocument: builder.query<DocumentDetail, { jobId: string; docId: string }>({
      query: ({ jobId, docId }) => `/jobs/${jobId}/documents/${docId}`,
    }),
    deleteDocument: builder.mutation<void, { jobId: string; docId: string }>({
      query: ({ jobId, docId }) => ({
        url: `/jobs/${jobId}/documents/${docId}`,
        method: "DELETE",
      }),
      invalidatesTags: ["Documents"],
    }),
  }),
});

export const {
  useCreateJobMutation,
  useGetJobQuery,
  useGetJobStatusQuery,
  useListDocumentsQuery,
  useGetDocumentQuery,
  useDeleteDocumentMutation,
} = jobsApi;
```

### 7.3 Create the Ingestion page — `src/app/ingestion/page.tsx`

```tsx
"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useCreateJobMutation } from "@/store/api/jobs-api";

export default function IngestionPage() {
  const [url, setUrl] = useState("");
  const [crawlAll, setCrawlAll] = useState(false);
  const [createJob, { isLoading, data: job }] = useCreateJobMutation();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!url.trim()) return;
    await createJob({ url: url.trim(), crawl_all_docs: crawlAll });
  };

  return (
    <main className="container mx-auto p-8">
      <h1 className="text-3xl font-bold mb-8">URL Ingestion</h1>

      {/* URL Input Form */}
      <Card className="mb-8">
        <CardHeader>
          <CardTitle>Submit Documentation URL</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <Input
              type="url"
              placeholder="https://docs.example.com/getting-started"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              required
            />
            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="crawlAll"
                checked={crawlAll}
                onChange={(e) => setCrawlAll(e.target.checked)}
                className="h-4 w-4"
              />
              <label htmlFor="crawlAll" className="text-sm">
                Crawl All Documentation Pages
              </label>
            </div>
            <Button type="submit" disabled={isLoading}>
              {isLoading ? "Submitting..." : "Start Ingestion"}
            </Button>
          </form>
        </CardContent>
      </Card>

      {/* Job Status */}
      {job && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              Job Created <Badge variant="secondary">{job.status}</Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">Job ID: {job.id}</p>
            <p className="text-sm">URL: {job.url}</p>
            <p className="text-sm">
              Progress: {job.processed_documents} / {job.total_documents} documents
            </p>
          </CardContent>
        </Card>
      )}
    </main>
  );
}
```

### 7.4 Create Staging Browser component — `src/features/staging/staging-browser.tsx`

```tsx
"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  useListDocumentsQuery,
  useGetDocumentQuery,
  useDeleteDocumentMutation,
  type DocumentItem,
} from "@/store/api/jobs-api";

interface StagingBrowserProps {
  jobId: string;
}

export function StagingBrowser({ jobId }: StagingBrowserProps) {
  const [selectedDocId, setSelectedDocId] = useState<string | null>(null);
  const { data: documents, isLoading } = useListDocumentsQuery(jobId);
  const { data: docDetail } = useGetDocumentQuery(
    { jobId, docId: selectedDocId! },
    { skip: !selectedDocId }
  );
  const [deleteDoc] = useDeleteDocumentMutation();

  if (isLoading) return <p>Loading documents...</p>;
  if (!documents?.length) return <p>No documents found for this job.</p>;

  return (
    <div className="grid grid-cols-12 gap-4">
      {/* Document List Panel */}
      <div className="col-span-4 border rounded-lg p-4 max-h-[80vh] overflow-y-auto">
        <h3 className="font-semibold mb-4">
          Documents ({documents.length})
        </h3>
        {documents.map((doc: DocumentItem) => (
          <div
            key={doc.id}
            className={`p-3 rounded cursor-pointer mb-2 border ${
              selectedDocId === doc.id ? "border-primary bg-accent" : "hover:bg-accent/50"
            }`}
            onClick={() => setSelectedDocId(doc.id)}
          >
            <p className="text-sm font-medium truncate">{doc.title || doc.url}</p>
            <div className="flex items-center gap-2 mt-1">
              <Badge variant={doc.status === "converted" ? "default" : "destructive"}>
                {doc.status}
              </Badge>
              {doc.word_count && (
                <span className="text-xs text-muted-foreground">
                  {doc.word_count} words
                </span>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Document Viewer Panel */}
      <div className="col-span-8">
        {docDetail ? (
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">{docDetail.title || "Untitled"}</CardTitle>
              <p className="text-sm text-muted-foreground">{docDetail.url}</p>
            </CardHeader>
            <CardContent>
              <Tabs defaultValue="markdown">
                <TabsList>
                  <TabsTrigger value="markdown">Markdown Preview</TabsTrigger>
                  <TabsTrigger value="raw">Raw Markdown</TabsTrigger>
                  <TabsTrigger value="html">Source HTML</TabsTrigger>
                </TabsList>
                <TabsContent value="markdown" className="prose max-w-none max-h-[60vh] overflow-y-auto">
                  {docDetail.markdown && (
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {docDetail.markdown}
                    </ReactMarkdown>
                  )}
                </TabsContent>
                <TabsContent value="raw">
                  <pre className="bg-muted p-4 rounded text-sm max-h-[60vh] overflow-y-auto whitespace-pre-wrap">
                    {docDetail.markdown || "No markdown content"}
                  </pre>
                </TabsContent>
                <TabsContent value="html">
                  <pre className="bg-muted p-4 rounded text-sm max-h-[60vh] overflow-y-auto whitespace-pre-wrap">
                    {docDetail.raw_html || "No HTML content"}
                  </pre>
                </TabsContent>
              </Tabs>
              <div className="flex gap-2 mt-4">
                <Button
                  variant="destructive"
                  size="sm"
                  onClick={() => {
                    deleteDoc({ jobId, docId: docDetail.id });
                    setSelectedDocId(null);
                  }}
                >
                  Remove Document
                </Button>
              </div>
            </CardContent>
          </Card>
        ) : (
          <div className="flex items-center justify-center h-64 border rounded-lg">
            <p className="text-muted-foreground">Select a document to view</p>
          </div>
        )}
      </div>
    </div>
  );
}
```

### 7.5 Create WebSocket progress hook — `src/hooks/use-job-progress.ts`

```typescript
"use client";

import { useEffect, useRef, useState, useCallback } from "react";

interface ProgressEvent {
  type: string;
  job_id: string;
  total?: number;
  completed?: number;
  current_url?: string;
  message?: string;
}

export function useJobProgress(jobId: string | null) {
  const [progress, setProgress] = useState<ProgressEvent | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  const connect = useCallback(() => {
    if (!jobId) return;

    const wsUrl = `${process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000"}/api/v1/ws/jobs/${jobId}/stream`;
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => setIsConnected(true);
    ws.onclose = () => {
      setIsConnected(false);
      // Reconnect after 3 seconds
      setTimeout(() => connect(), 3000);
    };
    ws.onmessage = (event) => {
      try {
        const data: ProgressEvent = JSON.parse(event.data);
        setProgress(data);
      } catch {
        // ignore non-JSON messages
      }
    };

    wsRef.current = ws;
  }, [jobId]);

  useEffect(() => {
    connect();
    return () => wsRef.current?.close();
  }, [connect]);

  return { progress, isConnected };
}
```

### 7.6 Add navigation link in layout

Update `src/app/layout.tsx` to include navigation:

```tsx
// Add inside <body> before {children}:
<nav className="border-b">
  <div className="container mx-auto flex items-center gap-6 p-4">
    <a href="/" className="font-bold text-lg">RAG Pipeline</a>
    <a href="/ingestion" className="text-sm hover:underline">Ingestion</a>
    <a href="/staging" className="text-sm hover:underline">Staging</a>
  </div>
</nav>
```

**Done when**: The `/ingestion` page renders with URL input form, and the staging browser component renders correctly when given a job ID.

---

## Task 8: Write Phase 2 Tests

**Working directory**: `rag-pipeline/apps/api/`

### 8.1 Create `tests/test_converter.py`

```python
"""Tests for the Markdown converter."""

from src.converters.markdown_converter import convert_html_to_markdown


def test_basic_html_conversion():
    """Simple HTML converts to Markdown with frontmatter."""
    html = "<html><head><title>Test Page</title></head><body><h1>Hello</h1><p>World</p></body></html>"
    result = convert_html_to_markdown(html, "https://example.com/test")
    assert result.error is None
    assert "---" in result.markdown  # frontmatter present
    assert "title:" in result.markdown
    assert "source_url:" in result.markdown
    assert result.word_count > 0


def test_sanitization_removes_scripts():
    """Script tags should be removed before conversion."""
    html = '<html><body><h1>Hi</h1><script>alert("xss")</script><p>Content</p></body></html>'
    result = convert_html_to_markdown(html, "https://example.com")
    assert "alert" not in result.markdown
    assert "script" not in result.markdown.lower()


def test_empty_html_returns_error():
    """Empty HTML should still return a result without crashing."""
    result = convert_html_to_markdown("", "https://example.com")
    # Should not raise, may have error or minimal content
    assert result is not None
```

### 8.2 Create `tests/test_link_discovery.py`

```python
"""Tests for link discovery."""

from src.crawlers.link_discovery import extract_links_with_selectors


def test_extracts_nav_links():
    """Should extract links from nav elements."""
    html = """
    <html><body>
    <nav>
        <a href="/docs/intro">Introduction</a>
        <a href="/docs/guide">Guide</a>
        <a href="https://external.com">External</a>
    </nav>
    </body></html>
    """
    links = extract_links_with_selectors(html, "https://example.com")
    hrefs = [l.href for l in links]
    assert "https://example.com/docs/intro" in hrefs
    assert "https://example.com/docs/guide" in hrefs
    # External link should be excluded
    assert not any("external.com" in h for h in hrefs)


def test_deduplicates_links():
    """Duplicate links should be removed."""
    html = """
    <html><body>
    <nav>
        <a href="/docs/intro">Intro</a>
        <a href="/docs/intro">Introduction</a>
    </nav>
    </body></html>
    """
    links = extract_links_with_selectors(html, "https://example.com")
    hrefs = [l.href for l in links]
    assert hrefs.count("https://example.com/docs/intro") == 1
```

**Done when**: `pytest tests/ -v` passes all tests (health + converter + link discovery).

---

## Phase 2 Done-When Checklist

- [ ] `POST /api/v1/jobs` with `{"url": "https://example.com", "crawl_all_docs": false}` returns 201
- [ ] Submitting `https://modelcontextprotocol.io/introduction` fetches and converts that page to Markdown
- [ ] With `crawl_all_docs: true`, the link discovery service finds related documentation pages
- [ ] Celery task chain executes: fetch → discover → fan-out convert → finalize
- [ ] Staging directory contains `html/` and `markdown/` files after a crawl
- [ ] `GET /api/v1/jobs/{id}/documents` returns the list of converted documents
- [ ] `GET /api/v1/jobs/{id}/documents/{doc_id}` returns Markdown + HTML content
- [ ] WebSocket endpoint at `/api/v1/ws/jobs/{id}/stream` accepts connections
- [ ] Next.js `/ingestion` page renders with URL input form and crawl toggle
- [ ] Staging browser component renders document list and preview panels
- [ ] All Markdown files have valid YAML frontmatter with `title`, `source_url`, `fetched_at`
- [ ] `pytest tests/ -v` passes all tests including converter and link discovery
