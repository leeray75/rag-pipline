# Phase 2, Subtask 2 — Markdown Converter + Celery Task Chain

> **Phase**: Phase 2 — Crawl & Convert
> **Prerequisites**: Phase 1 complete + Phase 2 Subtask 1 complete (dependencies installed, `fetcher.py` and `link_discovery.py` created)
> **Scope**: 2 files to create, 1 directory to ensure

---

## Relevant Technology Stack

| Package | Pinned Version | Purpose |
|---|---|---|
| Python | 3.13.x | Runtime |
| markitdown | 0.1.5 | HTML→Markdown conversion engine |
| Celery | 5.6.3 | Distributed task queue |
| Redis | 7.x | Celery broker |
| structlog | 25.4.0 | Structured logging |

### Key Imports from Subtask 1

These modules were created in Subtask 1 and are imported by the Celery tasks:

- `src.crawlers.fetcher` — exports `fetch_url`, `FetchResult`
- `src.crawlers.link_discovery` — exports `discover_doc_links`

---

## Step 1: Build the Markdown Converter Service

**Working directory**: `rag-pipeline/apps/api/src/converters/`

### 1.1 Create `markdown_converter.py`

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

---

## Step 2: Build the Celery Task Chain

**Working directory**: `rag-pipeline/apps/api/src/workers/`

### 2.1 Create `crawl_tasks.py`

This file defines the full crawl pipeline as a Celery workflow: `fetch_seed → discover_links → fan-out fetch_and_convert → finalize`.

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

---

## Files to Create/Modify

| Action | File Path |
|---|---|
| **Create** | `rag-pipeline/apps/api/src/converters/__init__.py` (if not exists) |
| **Create** | `rag-pipeline/apps/api/src/converters/markdown_converter.py` |
| **Create** | `rag-pipeline/apps/api/src/workers/crawl_tasks.py` |

---

## Done-When Checklist

- [ ] `rag-pipeline/apps/api/src/converters/markdown_converter.py` exists and exports `convert_html_to_markdown`, `ConversionResult`
- [ ] `convert_html_to_markdown("<html><body><h1>Test</h1><p>Hello</p></body></html>", "https://example.com")` returns valid Markdown with frontmatter
- [ ] `rag-pipeline/apps/api/src/workers/crawl_tasks.py` exists and exports `start_crawl_pipeline`, `fetch_seed_url`, `discover_links`, `fetch_and_convert_page`, `finalize_crawl`
- [ ] `start_crawl_pipeline(job_id, url)` dispatches tasks to Celery and completes without errors
- [ ] Celery task chain executes: fetch → discover → fan-out convert → finalize
- [ ] Staging directory contains `html/` and `markdown/` files after a crawl
- [ ] All Markdown files have valid YAML frontmatter with `title`, `source_url`, `fetched_at`

---

## Summary Report

Upon completion of this subtask, create a summary report at:
`rag-pipeline/ai-workspace/summary-reports/phase-2-subtask-2-converter-and-celery-summary.md`

The summary report must include:
- **Subtask**: Phase 2, Subtask 2 — Markdown Converter + Celery Task Chain
- **Status**: Complete / Partial / Blocked
- **Date**: {ISO 8601 date}
- **Files Created/Modified**: List every file path
- **Key Decisions**: Any deviations from the plan and why
- **Issues Encountered**: Problems and resolutions
- **Dependencies for Next Subtask**: What the next subtask needs to know
- **Verification Results**: Output of Done-When checklist items
