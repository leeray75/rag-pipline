"""Celery tasks for URL crawling and document conversion."""

import asyncio
import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from celery import chain, chord, group
from celery.exceptions import SoftTimeLimitExceeded
from sqlalchemy.orm import Session

from src.workers.celery_app import celery_app
from src.crawlers.fetcher import fetch_url, FetchResult
from src.crawlers.link_discovery import discover_doc_links
from src.converters.markdown_converter import convert_html_to_markdown
from src.database import sync_engine
from src.models.chunk import IngestionJob, JobStatus

import structlog

logger = structlog.get_logger()

STAGING_DIR = Path("/app/data/staging")


def _update_job_status_sync(job_id: str, status: JobStatus):
    """Synchronously update job status in the database."""
    try:
        with Session(sync_engine) as db:
            job = db.get(IngestionJob, job_id)
            if job:
                job.status = status
                db.commit()
                logger.info("job_status_updated", job_id=job_id, status=status.value)
    except Exception as e:
        logger.error("sync_status_update_error", job_id=job_id, status=status.value, error=str(e))


class CrawlBaseTask(celery_app.Task):
    """Base task class that updates job status on failure."""

    abstract = True

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        job_id = None
        if kwargs:
            job_id = kwargs.get("job_id")
        if not job_id and args and len(args) > 1:
            job_id = args[1]
        if job_id:
            _update_job_status_sync(job_id, JobStatus.FAILED)
        super().on_failure(exc, task_id, args, kwargs, einfo)


def _ensure_job_dir(job_id: str) -> Path:
    """Create and return the staging directory for a job."""
    job_dir = STAGING_DIR / job_id
    (job_dir / "html").mkdir(parents=True, exist_ok=True)
    (job_dir / "markdown").mkdir(parents=True, exist_ok=True)
    return job_dir


@celery_app.task(bind=True, base=CrawlBaseTask, name="crawl.fetch_seed_url", acks_late=True, reject_on_worker_lost=True, time_limit=120, soft_time_limit=90)
def fetch_seed_url(self, job_id: str, url: str, use_browser: bool = False):
    """Fetch the seed URL HTML. Returns serialized FetchResult."""
    try:
        result = asyncio.run(fetch_url(url, use_browser=use_browser))
    except SoftTimeLimitExceeded:
        _update_job_status_sync(job_id, JobStatus.FAILED)
        raise

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


@celery_app.task(bind=True, base=CrawlBaseTask, name="crawl.discover_links", acks_late=True, reject_on_worker_lost=True, time_limit=60, soft_time_limit=45)
def discover_links(self, seed_result: dict, crawl_all: bool = True):
    """Discover documentation page links from the seed URL."""
    try:
        if not crawl_all:
            # Single page mode — just return the seed URL
            return {
                "job_id": seed_result["job_id"],
                "links": [{"href": seed_result["url"], "title": "Seed Page", "source": "direct"}],
            }

        html = Path(seed_result["html_path"]).read_text(encoding="utf-8")
        links = asyncio.run(discover_doc_links(html, seed_result["url"]))
    except SoftTimeLimitExceeded:
        _update_job_status_sync(seed_result.get("job_id", "unknown"), JobStatus.FAILED)
        raise

    # Always include the seed URL
    seed_in_list = any(link.href == seed_result["url"] for link in links)
    link_dicts = [{"href": l.href, "title": l.title, "source": l.source} for l in links]
    if not seed_in_list:
        link_dicts.insert(0, {"href": seed_result["url"], "title": "Seed Page", "source": "direct"})

    logger.info("links_discovered", job_id=seed_result["job_id"], count=len(link_dicts))
    return {"job_id": seed_result["job_id"], "links": link_dicts}


@celery_app.task(bind=True, base=CrawlBaseTask, name="crawl.fetch_and_convert_page", acks_late=True, reject_on_worker_lost=True, time_limit=120, soft_time_limit=90, rate_limit="1/s")
def fetch_and_convert_page(self, job_id: str, link: dict, doc_index: int):
    """Fetch a single page, convert to Markdown, and save to staging."""
    url = link["href"]
    title = link.get("title", "")

    try:
        # Fetch
        result = asyncio.run(fetch_url(url, use_browser=False))
    except SoftTimeLimitExceeded:
        _update_job_status_sync(job_id, JobStatus.FAILED)
        raise
    except Exception as e:
        return {
            "job_id": job_id,
            "doc_index": doc_index,
            "url": url,
            "status": "failed",
            "error": str(e),
        }

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


@celery_app.task(bind=True, base=CrawlBaseTask, name="crawl.finalize_crawl", acks_late=True, reject_on_worker_lost=True, time_limit=60, soft_time_limit=45)
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

    # Update job status in database using sync session
    try:
        with Session(sync_engine) as db:
            job = db.get(IngestionJob, job_id)
            if job:
                if successful and not failed:
                    job.status = JobStatus.COMPLETED
                elif successful:
                    job.status = JobStatus.PROCESSING
                else:
                    job.status = JobStatus.FAILED
                job.total_documents = len(results)
                job.processed_documents = len(successful)
                db.commit()
    except Exception as e:
        logger.error("failed_to_update_job_status", job_id=job_id, error=str(e))

    return manifest


@celery_app.task(bind=True, name="crawl.handle_chord_error")
def handle_crawl_chord_error(self, result=None, exc=None, task_id=None, args=None):
    """Handle chord member failures and update job status."""
    # Extract job_id from the result dict
    job_id = "unknown"
    if isinstance(result, dict):
        job_id = result.get("job_id", "unknown")
    elif isinstance(result, list):
        for r in result:
            if isinstance(r, dict) and "job_id" in r:
                job_id = r["job_id"]
                break

    logger.error(
        "chord_member_failed",
        job_id=job_id,
        error=str(exc) if exc else str(result),
        task_id=task_id,
    )
    _update_job_status_sync(job_id, JobStatus.FAILED)


@celery_app.task(bind=True, base=CrawlBaseTask, name="crawl.fan_out_and_finalize")
def _fan_out_and_finalize(self, discovery_result: dict):
    """Fan out fetch_and_convert tasks for all discovered links, then finalize."""
    job_id = discovery_result["job_id"]
    links = discovery_result["links"]

    # Create a group of fetch_and_convert tasks
    tasks = [
        fetch_and_convert_page.s(job_id, link, idx)
        for idx, link in enumerate(links)
    ]

    # Use chord with on_error callback
    callback = finalize_crawl.s(job_id=job_id)
    error_handler = handle_crawl_chord_error.s()

    job = chord(tasks)(callback.on_error(error_handler))
    return {"job_id": job_id, "task_count": len(tasks), "chord_id": str(job.id)}


def start_crawl_pipeline(job_id: str, url: str, crawl_all: bool = True):
    """Kick off the full crawl pipeline as a Celery workflow.

    Pipeline: fetch_seed → discover_links → fan-out fetch_and_convert → finalize
    """
    workflow = chain(
        fetch_seed_url.s(job_id, url, use_browser=False),
        discover_links.s(crawl_all=crawl_all),
        _fan_out_and_finalize.s(),
    )
    result = workflow.apply_async()

    # Store task ID on the job for revocation on retry
    try:
        with Session(sync_engine) as db:
            job = db.get(IngestionJob, job_id)
            if job:
                job.celery_task_id = str(result.id)
                db.commit()
    except Exception as e:
        logger.error("failed_to_store_celery_task_id", job_id=job_id, error=str(e))

    return result


@celery_app.task(name="crawl.reap_stuck_jobs")
def reap_stuck_jobs():
    """Periodic task to mark jobs stuck in CRAWLING for too long as FAILED."""
    threshold = datetime.utcnow() - timedelta(minutes=30)
    with Session(sync_engine) as db:
        from sqlalchemy import select
        stuck = db.execute(
            select(IngestionJob).where(
                IngestionJob.status == JobStatus.CRAWLING,
                IngestionJob.updated_at < threshold
            )
        ).scalars().all()
        for job in stuck:
            job.status = JobStatus.FAILED
            logger.warning("reaped_stuck_job", job_id=str(job.id), updated_at=str(job.updated_at))
        if stuck:
            db.commit()
        logger.info("reap_stuck_jobs_complete", reaped=len(stuck))