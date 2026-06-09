# Summary Report: Crawl Pipeline Reliability Fix

**Date**: 2026-06-08
**Version**: 1.2.4
**Branch**: `fix/crawl-pipeline-fix`

---

## Problem

Job `782a1d6f-5be3-45e6-b82e-80ed82450078` (and other jobs) were getting stuck at `CRAWLING` status and never transitioning to `PROCESSING`, `AUDITING`, or `COMPLETED`.

### Root Causes Identified

1. **No DB status update in `finalize_crawl`**: The Celery task only saved a manifest file — it never updated the job status in the database.
2. **No error handling for failed tasks**: When a Celery task failed, the job status was never updated to `FAILED`.
3. **Chord silent failure**: If any task in a Celery chord group failed or hung, the `finalize_crawl` callback never fired (chords wait for ALL tasks).
4. **No task timeouts**: Tasks could run indefinitely, blocking workers.
5. **No resource cleanup**: Playwright browser processes were not always closed on timeout.

---

## Solution Implemented

### Phase 1: Sync DB Status Update in `finalize_crawl`

**File**: `apps/api/src/database.py`

Added synchronous SQLAlchemy engine and session factory for use in Celery workers (avoids `asyncio.run()` issues with gevent/eventlet):

```python
_sync_engine = create_engine(_make_sync_url(settings.database_url), ...)
sync_engine = _sync_engine
SyncSession = sessionmaker(sync_engine, expire_on_commit=False)
```

**File**: `apps/api/src/workers/crawl_tasks.py`

Updated `finalize_crawl` to update job status using sync session:

```python
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
```

### Phase 2: Base Task Class with `on_failure` Handler

**File**: `apps/api/src/workers/crawl_tasks.py`

Created `CrawlBaseTask` that overrides `on_failure` to automatically update job status to `FAILED`:

```python
class CrawlBaseTask(celery_app.Task):
    abstract = True

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        job_id = kwargs.get("job_id") if kwargs else (args[1] if len(args) > 1 else None)
        if job_id:
            _update_job_status_sync(job_id, JobStatus.FAILED)
        super().on_failure(exc, task_id, args, kwargs, einfo)
```

All crawl tasks now use `base=CrawlBaseTask` and handle `SoftTimeLimitExceeded` explicitly.

### Phase 3: Chord Error Handler

**File**: `apps/api/src/workers/crawl_tasks.py`

Added `handle_crawl_chord_error` task as `on_error` callback for the crawl chord:

```python
callback = finalize_crawl.s(job_id=job_id)
error_handler = handle_crawl_chord_error.s()
job = chord(tasks)(callback.on_error(error_handler))
```

Also added `CELERY_CHORD_UNLOCK_MAX_RETRIES = 10` to prevent infinite unlock retries.

### Phase 4: Task Timeouts

All crawl tasks now have `time_limit` and `soft_time_limit`:

| Task | time_limit | soft_time_limit |
|------|-----------|-----------------|
| `fetch_seed_url` | 120s | 90s |
| `discover_links` | 60s | 45s |
| `fetch_and_convert_page` | 120s | 90s |
| `finalize_crawl` | 60s | 45s |

Tasks catch `SoftTimeLimitExceeded` and update job status before re-raising.

### Phase 5: Retry Endpoint with Safety Guards

**File**: `apps/api/src/routers/jobs.py`

Added `POST /jobs/{job_id}/retry` endpoint:

- Uses conditional SQL update to prevent concurrent retries (returns HTTP 409)
- Revokes existing Celery task via `celery_app.control.revoke()`
- Stores `celery_task_id` on `IngestionJob` model for revocation

### Broker Reliability

All crawl tasks now include:
- `acks_late=True`: Message is acknowledged after execution (re-queued on crash)
- `reject_on_worker_lost=True`: Message is re-queued if worker disconnects

### Stuck Job Reaper

Added `reap_stuck_jobs` periodic Celery Beat task:
- Runs every 30 minutes
- Marks jobs stuck in `CRAWLING` for >30 minutes as `FAILED`
- Registered in `celery_app.conf.beat_schedule`
- `celery-beat` service added to Docker Compose (dev and prod)

### Playwright Cleanup

**File**: `apps/api/src/crawlers/fetcher.py`

Added `try/finally` blocks in `fetch_with_browser()` to ensure browser and context are always closed:

```python
browser = None
context = None
try:
    ...
finally:
    if browser:
        try:
            await browser.close()
        except Exception:
            pass
    if context:
        try:
            await context.close()
        except Exception:
            pass
```

---

## Files Modified

| File | Change |
|------|--------|
| `apps/api/src/database.py` | Added sync engine and `SyncSession` |
| `apps/api/src/workers/crawl_tasks.py` | Full rewrite with all fixes |
| `apps/api/src/workers/celery_app.py` | Added `CELERY_CHORD_UNLOCK_MAX_RETRIES`, beat schedule |
| `apps/api/src/routers/jobs.py` | Added retry endpoint |
| `apps/api/src/models/chunk.py` | Added `celery_task_id` column |
| `apps/api/src/crawlers/fetcher.py` | Added Playwright cleanup |
| `apps/api/pyproject.toml` | Added `psycopg2-binary` dependency |
| `infra/docker-compose.yml` | Added `celery-beat` service |
| `infra/docker-compose.dev.yml` | Added `celery-beat` service |
| `apps/api/alembic/versions/...` | Migration for `celery_task_id` column |

## Files Created

| File | Purpose |
|------|---------|
| `ai-workspace/plans/crawl-fix-plan.md` | Detailed fix plan |
| `ai-workspace/summary-reports/crawl-pipeline-fix-2026-06-08.md` | This report |
| `apps/api/alembic/versions/2026_06_08_2100_add_celery_task_id_to_ingestion_jobs.py` | DB migration |

---

## Version Changes

| Package | Old Version | New Version |
|---------|------------|-------------|
| Monorepo (package.json) | 1.2.3 | **1.2.4** |
| API (pyproject.toml) | 0.3.0 | **0.3.1** |

---

## Testing Checklist

- [ ] `finalize_crawl` updates status using sync session, no `asyncio.run()` call
- [ ] `on_failure` base class correctly reads `job_id` from `kwargs`
- [ ] `SoftTimeLimitExceeded` updates job to `FAILED` before hard kill
- [ ] Chord `on_error` callback fires when a member task raises an exception
- [ ] `CELERY_CHORD_UNLOCK_MAX_RETRIES` prevents infinite unlock retries
- [ ] Retry endpoint rejects concurrent retries for the same job (HTTP 409)
- [ ] Retry endpoint revokes the original Celery task before re-queuing
- [ ] Stuck job reaper marks jobs `FAILED` after the configured threshold
- [ ] Playwright browser is closed in `finally` even when the task times out
- [ ] Alembic migration applies cleanly on a fresh schema
- [ ] Full end-to-end crawl completes and transitions to `COMPLETED`
- [ ] Partial failure (some pages fail) results in `PROCESSING` status, not stuck
- [ ] Worker crash with `acks_late=True` re-queues the message correctly

---

## Deployment

```bash
cd rag-pipline/infra
docker compose -f docker-compose.yml build
docker compose -f docker-compose.yml up -d
docker compose exec api alembic upgrade head
```

---

## Rollback Plan

```bash
cd rag-pipline
git checkout HEAD~2  # Revert both commits
docker compose -f infra/docker-compose.yml up -d --force-recreate api celery-worker celery-beat
```

---

*Report generated: 2026-06-08*