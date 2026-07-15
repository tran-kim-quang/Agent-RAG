import os

from celery import Celery
from dotenv import load_dotenv

load_dotenv()

redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
celery_app = Celery(
    "agent_rag",
    broker=redis_url,
    backend=os.getenv("CELERY_RESULT_BACKEND", redis_url),
    include=["backend.src.tasks.jobs"],
)
celery_app.conf.update(
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_track_started=True,
    broker_connection_retry_on_startup=True,
    result_expires=3600,
    worker_prefetch_multiplier=1,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    beat_schedule={
        "recover-stale-tasks": {
            "task": "agent_rag.recover_stale",
            "schedule": 300.0,
        }
    },
)
