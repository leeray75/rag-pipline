"""Celery application configuration."""

from celery import Celery
from celery.schedules import crontab

from src.config import settings

celery_app = Celery(
    "rag_pipeline",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    # Prevent infinite retries on chord unlock
    CELERY_CHORD_UNLOCK_MAX_RETRIES = 10,
)

# Beat schedule for periodic tasks
celery_app.conf.beat_schedule = {
    "reap-stuck-jobs": {
        "task": "crawl.reap_stuck_jobs",
        "schedule": crontab(minute="*/30"),  # Every 30 minutes
    },
}

# Auto-discover tasks in workers module
celery_app.autodiscover_tasks(["src.workers"])
