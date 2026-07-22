import os
import logging

from celery import Celery
from celery.signals import worker_ready
from dotenv import load_dotenv

load_dotenv()

redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
visibility_timeout = int(os.getenv("CELERY_VISIBILITY_TIMEOUT_SECONDS", "21600"))
logger = logging.getLogger(__name__)
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
    broker_transport_options={"visibility_timeout": visibility_timeout},
    result_backend_transport_options={"visibility_timeout": visibility_timeout},
    visibility_timeout=visibility_timeout,
    task_routes={
        "agent_rag.chat": {"queue": "chat"},
        "agent_rag.ingest": {"queue": "ingest"},
        "agent_rag.recover_stale": {"queue": "maintenance"},
    },
    beat_schedule={
        "recover-stale-tasks": {
            "task": "agent_rag.recover_stale",
            "schedule": 300.0,
        }
    },
)


@worker_ready.connect
def warm_chat_models(**_) -> None:
    if os.getenv("WORKER_ROLE") != "chat":
        return
    try:
        from backend.src.infrastructure import get_ollama_embeddings
        from backend.src.retrieval.reranker import get_reranker

        get_ollama_embeddings().embed_query("warmup")
        get_reranker().warmup()
        logger.info("Chat models warmed and ready")
    except Exception:
        logger.exception("Chat model warmup failed; worker remains available for retries")
