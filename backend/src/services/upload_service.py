from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Lock
from typing import Callable
from uuid import uuid4

from backend.src.tools.processData_tool import process_and_ingest_uploaded_file

logger = logging.getLogger(__name__)

ProcessUploadedFileFn = Callable[[str, bytes, Callable[[str, str, dict | None], None] | None], dict]


class UploadJobService:
    def __init__(
        self,
        process_uploaded_file: ProcessUploadedFileFn = process_and_ingest_uploaded_file,
        max_workers: int = 2,
    ) -> None:
        self._process_uploaded_file = process_uploaded_file
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="ingest-worker")
        self._job_lock = Lock()
        self._jobs: dict[str, dict] = {}

    def create_upload_job(self, file_name: str, file_bytes: bytes) -> dict:
        job = self._create_job(file_name)
        with self._job_lock:
            self._jobs[job["job_id"]] = job
        self._executor.submit(self._run_ingest_job, job["job_id"], file_name, file_bytes)
        return dict(job)

    def get_upload_job(self, job_id: str) -> dict | None:
        with self._job_lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            return dict(job)

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _create_job(self, file_name: str) -> dict:
        timestamp = self._now_iso()
        return {
            "job_id": uuid4().hex,
            "file_name": file_name,
            "status": "queued",
            "phase": "queued",
            "message": f"Queued '{file_name}' for background ingest.",
            "raw_path": None,
            "processed_path": None,
            "metadata_path": None,
            "chunk_count": None,
            "indexed_chunks": 0,
            "total_chunks": None,
            "source_name": None,
            "error": None,
            "created_at": timestamp,
            "updated_at": timestamp,
        }

    def _update_job(self, job_id: str, **updates) -> None:
        with self._job_lock:
            job = self._jobs[job_id]
            job.update(updates)
            job["updated_at"] = self._now_iso()

    def _run_ingest_job(self, job_id: str, file_name: str, file_bytes: bytes) -> None:
        logger.info("[upload/service] Starting background ingest job: job_id=%s file_name=%s", job_id, file_name)
        self._update_job(job_id, status="processing", phase="start", message=f"Started ingest for '{file_name}'.")

        def progress_callback(phase: str, message: str, details: dict | None = None) -> None:
            logger.info("[upload/service] Progress update: job_id=%s phase=%s message=%s", job_id, phase, message)
            updates = {
                "status": "processing",
                "phase": phase,
                "message": message,
            }
            if details:
                updates.update(details)
            self._update_job(job_id, **updates)

        try:
            result = self._process_uploaded_file(
                file_name=file_name,
                file_bytes=file_bytes,
                progress_callback=progress_callback,
            )
            self._update_job(
                job_id,
                status="completed",
                phase="done",
                message=f"Processed '{result['source_name']}' successfully.",
                raw_path=result["raw_path"],
                processed_path=result["processed_path"],
                metadata_path=result["metadata_path"],
                chunk_count=result["chunk_count"],
                indexed_chunks=result["chunk_count"],
                total_chunks=result["chunk_count"],
                source_name=result["source_name"],
            )
            logger.info("[upload/service] Background ingest completed: job_id=%s result=%s", job_id, result)
        except Exception as exc:
            logger.exception("[upload/service] Background ingest failed: job_id=%s file_name=%s", job_id, file_name)
            self._update_job(
                job_id,
                status="failed",
                phase="failed",
                message=f"Document ingest failed for '{file_name}'.",
                error=str(exc),
            )
