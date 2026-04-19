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
