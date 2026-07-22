import logging
import os

from backend.src.tasks.celery_app import celery_app
from backend.src.tasks.dependencies import get_task_dependencies
from backend.src.tasks.retry_policy import is_retryable_task_error

logger = logging.getLogger(__name__)
max_retries = int(os.getenv("TASK_MAX_RETRIES", "3"))
stale_task_minutes = int(os.getenv("STALE_TASK_MINUTES", "60"))


@celery_app.task(name="agent_rag.recover_stale")
def recover_stale_tasks() -> dict:
    uploads, chats = get_task_dependencies().recovery.fail_stale_tasks(stale_task_minutes)
    return {"uploads_failed": uploads, "chats_failed": chats}


@celery_app.task(bind=True, name="agent_rag.chat", max_retries=max_retries)
def run_chat_task(self, run_id: str, chat_session_id: str, user_id: str, message: str) -> None:
    runner = get_task_dependencies().chat_runner
    try:
        runner.run(run_id, chat_session_id, user_id, message, self.request.retries + 1, self.request.hostname)
    except Exception as exc:
        logger.exception("Chat task failed: run_id=%s", run_id)
        if self.request.retries < max_retries and is_retryable_task_error(exc):
            runner.mark_retry(run_id, exc)
            raise self.retry(exc=exc, countdown=min(60, 2 ** (self.request.retries + 1)))
        runner.mark_failed(run_id, exc)
        raise


@celery_app.task(bind=True, name="agent_rag.ingest", max_retries=max_retries)
def run_upload_task(self, job_id: str, user_id: str, file_name: str, object_key: str) -> None:
    runner = get_task_dependencies().upload_runner
    try:
        runner.run(job_id, user_id, file_name, object_key, self.request.retries + 1, self.request.hostname)
    except Exception as exc:
        logger.exception("Upload task failed: job_id=%s", job_id)
        if self.request.retries < max_retries and is_retryable_task_error(exc):
            runner.mark_retry(job_id, file_name, exc)
            raise self.retry(exc=exc, countdown=min(60, 2 ** (self.request.retries + 1)))
        runner.mark_failed(job_id, file_name, exc)
        raise
