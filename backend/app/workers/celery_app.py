"""Celery application.

WHY A SEPARATE PROCESS
----------------------
This is the part of SafeMed that runs when nobody is using it. A web server
answers a request and stops; it cannot watch the FDA feed overnight.

Celery Beat puts a job on a Redis queue on a schedule, and a Celery worker -
its own process, its own container - picks the job up and runs it. If a job
fails it can be retried without being lost, and the worker can be seen running
independently, which is what makes "nobody opened the app" demonstrably true
rather than a claim.
"""
from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "safemed",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # If a worker dies mid-job the task returns to the queue instead of
    # vanishing.
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

celery_app.conf.beat_schedule = {
    "check-fda-recalls-hourly": {
        "task": "app.workers.tasks.check_recalls",
        "schedule": crontab(minute=0),          # top of every hour
    },
    "explain-findings": {
        "task": "app.workers.tasks.explain_findings",
        "schedule": crontab(minute="*/10"),
    },
    "refresh-dose-statuses": {
        "task": "app.workers.tasks.refresh_dose_statuses",
        "schedule": crontab(minute="*/15"),     # every 15 minutes
    },
}
