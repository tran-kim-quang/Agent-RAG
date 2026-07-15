from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re
from typing import Callable
from uuid import uuid4

from backend.src.core.repositories import ObjectStorage, UploadRepository
from backend.src.db import UploadJob


class UploadJobService:
    def __init__(
        self,
        uploads: UploadRepository,
        storage: ObjectStorage,
        enqueue: Callable[[str, str, str, str], str] | None = None,
    ) -> None:
        self._uploads = uploads
        self._storage = storage
        self._enqueue = enqueue or self._enqueue_task

    def create_upload_job(
        self,
        file_name: str,
        file_bytes: bytes,
        user_id: str,
        content_type: str | None = None,
    ) -> dict:
        job_id = uuid4().hex
        safe_name = Path(file_name.replace("\\", "/")).name.strip()
        if not safe_name:
            raise ValueError("Uploaded file name is empty.")
        object_name = re.sub(r"[^A-Za-z0-9._-]", "_", safe_name)
        message = f"Queued '{safe_name}' for background ingest."
        object_key = f"users/{user_id}/uploads/{job_id}/raw/{object_name}"
        self._uploads.create(
            job_id,
            user_id,
            safe_name,
            message,
            content_type=content_type,
            size_bytes=len(file_bytes),
        )
        try:
            self._storage.put_bytes(object_key, file_bytes, content_type or "application/octet-stream")
            self._uploads.update(job_id, raw_object_key=object_key, phase="stored", progress=1)
            task_id = self._enqueue(job_id, user_id, safe_name, object_key)
            self._uploads.update(job_id, task_id=task_id)
        except Exception as exc:
            self._uploads.update(
                job_id,
                status="failed",
                phase="failed",
                message=f"Could not queue '{safe_name}'.",
                error=str(exc),
                finished_at=datetime.now(timezone.utc),
            )
            raise
        item = self._uploads.get(job_id)
        if item is None:
            raise RuntimeError("Upload job was not persisted.")
        return self._job_to_dict(item)

    def get_upload_job(self, job_id: str, user_id: str | None = None, is_admin: bool = False) -> dict | None:
        item = self._uploads.get(job_id)
        if item is None or (user_id is not None and not is_admin and item.user_id != user_id):
            return None
        return self._job_to_dict(item)

    def list_upload_jobs(self, limit: int = 20, user_id: str | None = None) -> list[dict]:
        return [self._job_to_dict(job) for job in self._uploads.list(user_id=user_id, limit=limit)]

    def get_download(self, job_id: str, user_id: str, is_admin: bool = False) -> tuple[bytes, str, str] | None:
        item = self._uploads.get(job_id)
        if item is None or (not is_admin and item.user_id != user_id) or not item.raw_object_key:
            return None
        return (
            self._storage.get_bytes(item.raw_object_key),
            item.file_name,
            item.content_type or "application/octet-stream",
        )

    @staticmethod
    def _enqueue_task(job_id: str, user_id: str, file_name: str, object_key: str) -> str:
        from backend.src.tasks.jobs import run_upload_task

        return run_upload_task.apply_async(args=[job_id, user_id, file_name, object_key]).id

    @staticmethod
    def _job_to_dict(job: UploadJob) -> dict:
        return {
            "job_id": job.id,
            "user_id": job.user_id,
            "file_name": job.file_name,
            "status": job.status,
            "phase": job.phase,
            "message": job.message,
            "raw_path": job.raw_path,
            "processed_path": job.processed_path,
            "metadata_path": job.metadata_path,
            "raw_object_key": job.raw_object_key,
            "processed_object_key": job.processed_object_key,
            "metadata_object_key": job.metadata_object_key,
            "chunk_count": job.chunk_count,
            "indexed_chunks": job.indexed_chunks,
            "total_chunks": job.total_chunks,
            "source_name": job.source_name,
            "progress": job.progress,
            "attempt_count": job.attempt_count,
            "error": job.error,
            "created_at": job.created_at.isoformat(),
            "updated_at": job.updated_at.isoformat(),
        }
