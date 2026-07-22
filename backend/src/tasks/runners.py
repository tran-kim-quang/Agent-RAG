from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from backend.src.core.repositories import ChatRepository, DocumentRepository, KnowledgeBaseRepository, ObjectStorage, UploadRepository
from backend.src.monitoring import agent_run_monitor
from backend.src.security import bind_user
from backend.src.services.chat_service import ChatService
from backend.src.infrastructure.token_stream import ChatTokenStreamPublisher


class ChatTaskRunner:
    def __init__(
        self,
        chats: ChatRepository,
        chat_service: ChatService,
        token_stream: ChatTokenStreamPublisher | None = None,
    ) -> None:
        self.chats = chats
        self.chat_service = chat_service
        self.token_stream = token_stream or ChatTokenStreamPublisher()

    def run(self, run_id: str, chat_session_id: str, user_id: str, message: str, attempt: int, worker_id: str) -> None:
        now = datetime.now(timezone.utc)
        self.token_stream.start(run_id, attempt)
        self.chats.update_run(run_id, status="processing", attempt_count=attempt, worker_id=worker_id, heartbeat_at=now, started_at=now)
        self.chats.update_session(chat_session_id, status="processing", attempt_count=attempt, worker_id=worker_id, heartbeat_at=now, started_at=now)

        def event_sink(event: dict, status: str | None) -> None:
            self.chats.append_event(run_id, event, status=status or "processing")

        with agent_run_monitor.bind_run(run_id), agent_run_monitor.bind_event_sink(event_sink), bind_user(user_id):
            agent_run_monitor.append_event("chat_received", "Worker started the agent workflow.", {"message_length": len(message)}, status="processing")
            session = self.chats.get(chat_session_id)
            history = [] if session is None else [{"role": item.role, "content": item.content} for item in session.messages]
            answer = self.chat_service.answer(
                message,
                chat_session_id,
                history,
                token_callback=lambda token: self.token_stream.token(run_id, token),
            )
            agent_run_monitor.append_event("chat_completed", "Final answer generated.", {"answer_length": len(answer)}, status="processing")
        now = datetime.now(timezone.utc)
        self.chats.complete_run(run_id, answer, now)
        self.token_stream.complete(run_id)

    def mark_retry(self, run_id: str, error: Exception) -> None:
        self.chats.update_run(run_id, status="retrying", error=str(error), heartbeat_at=datetime.now(timezone.utc))
        run = self.chats.get_run(run_id)
        if run is not None: self.chats.update_session(run.session_id, status="retrying", error=str(error))
        self.token_stream.status(run_id, "retrying", "The agent run is retrying.")

    def mark_failed(self, run_id: str, error: Exception) -> None:
        now = datetime.now(timezone.utc)
        self.chats.update_run(run_id, status="failed", error=str(error), heartbeat_at=now, finished_at=now)
        run = self.chats.get_run(run_id)
        if run is not None: self.chats.update_session(run.session_id, status="failed", error=str(error), heartbeat_at=now, finished_at=now)
        self.token_stream.error(run_id, str(error))


class UploadTaskRunner:
    def __init__(
        self,
        uploads: UploadRepository,
        documents: DocumentRepository,
        storage: ObjectStorage,
        knowledge_bases: KnowledgeBaseRepository,
        ingest: Callable[..., dict],
    ) -> None:
        self.uploads = uploads
        self.documents = documents
        self.storage = storage
        self.knowledge_bases = knowledge_bases
        self.ingest = ingest

    def run(self, job_id: str, user_id: str, file_name: str, object_key: str, attempt: int, worker_id: str) -> None:
        now = datetime.now(timezone.utc)
        current = self.uploads.get(job_id)
        if current is None or current.status not in {"queued", "retrying", "processing"}:
            return
        previous_attempts = current.attempt_count if current is not None else 0
        attempt_count = max(attempt, previous_attempts + 1) if attempt == 1 else max(attempt, previous_attempts)
        self.uploads.update(job_id, status="processing", phase="download", message=f"Worker is downloading '{file_name}' from object storage.", attempt_count=attempt_count, worker_id=worker_id, heartbeat_at=now, started_at=now, finished_at=None, error=None, progress=2)

        def progress(phase: str, message: str, details: dict | None = None) -> None:
            updates = {"status": "processing", "phase": phase, "message": message, "heartbeat_at": datetime.now(timezone.utc), "progress": _phase_progress(phase)}
            if details: updates.update(details)
            self.uploads.update(job_id, **updates)

        result = self.ingest(file_name=file_name, file_bytes=self.storage.get_bytes(object_key), progress_callback=progress, owner_id=user_id)
        prefix = f"users/{user_id}/uploads/{job_id}/processed"
        processed_key = self.storage.put_path(f"{prefix}/{Path(result['processed_path']).name}", result["processed_path"], "text/markdown")
        metadata_key = self.storage.put_path(f"{prefix}/{Path(result['metadata_path']).name}", result["metadata_path"], "application/json")
        now = datetime.now(timezone.utc)
        self.uploads.update(
            job_id, status="processing", phase="finalize", message=f"Finalizing '{result['source_name']}'.",
            raw_path=result["raw_path"], processed_path=result["processed_path"], metadata_path=result["metadata_path"],
            processed_object_key=processed_key, metadata_object_key=metadata_key, chunk_count=result["chunk_count"],
            indexed_chunks=result["chunk_count"], total_chunks=result["chunk_count"], source_name=result["source_name"],
            progress=98, error=None, heartbeat_at=now,
        )
        job = self.uploads.get(job_id)
        if job is not None: self.documents.upsert_from_upload(job)
        self.knowledge_bases.bump_version(user_id)
        self.uploads.update(job_id, status="completed", phase="done", message=f"Processed '{result['source_name']}' successfully.", progress=100, heartbeat_at=now, finished_at=now)

    def mark_retry(self, job_id: str, file_name: str, error: Exception) -> None:
        self.uploads.update(job_id, status="retrying", phase="retrying", message=f"Ingest failed; retrying '{file_name}'.", error=str(error), heartbeat_at=datetime.now(timezone.utc))

    def mark_failed(self, job_id: str, file_name: str, error: Exception) -> None:
        now = datetime.now(timezone.utc)
        self.uploads.update(job_id, status="failed", phase="failed", message=f"Document ingest failed for '{file_name}'.", error=str(error), heartbeat_at=now, finished_at=now)


def _phase_progress(phase: str) -> int:
    return {"start": 5, "save_raw": 10, "process": 20, "write_processed": 35, "clean": 45, "chunk": 55, "chunk_complete": 65, "embed": 70, "index": 85, "index_complete": 95, "done": 98}.get(phase, 50)
