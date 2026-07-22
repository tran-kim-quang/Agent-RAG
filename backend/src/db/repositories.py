from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import delete, select, update
from sqlalchemy.orm import selectinload

from backend.src.db.models import ChatMessage, ChatRun, ChatSession, Document, RefreshToken, UploadJob, User
from backend.src.db.session import Database


class SqlUserRepository:
    def __init__(self, database: Database) -> None: self.database = database
    def get(self, user_id: str) -> User | None:
        with self.database.session() as session: return session.get(User, user_id)
    def get_by_email(self, email: str) -> User | None:
        with self.database.session() as session: return session.scalar(select(User).where(User.email == email.lower()))
    def create(self, email: str, password_hash: str, role: str = "user") -> User:
        user = User(id=uuid4().hex, email=email.lower(), password_hash=password_hash, role=role)
        with self.database.session() as session: session.add(user)
        return user
    def list(self, limit: int = 100) -> list[User]:
        with self.database.session() as session: return list(session.scalars(select(User).order_by(User.created_at.desc()).limit(limit)))


class SqlRefreshTokenRepository:
    def __init__(self, database: Database) -> None: self.database = database
    def save(self, user_id: str, jti_hash: str, expires_at: datetime) -> None:
        with self.database.session() as session: session.add(RefreshToken(id=uuid4().hex, user_id=user_id, jti_hash=jti_hash, expires_at=expires_at))
    def consume(self, jti_hash: str) -> str | None:
        now = datetime.now(timezone.utc)
        with self.database.session() as session:
            token = session.scalar(select(RefreshToken).where(RefreshToken.jti_hash == jti_hash).with_for_update())
            if token is None or token.revoked_at is not None or _as_utc(token.expires_at) <= now: return None
            token.revoked_at = now
            return token.user_id
    def revoke(self, jti_hash: str) -> None:
        with self.database.session() as session:
            token = session.scalar(select(RefreshToken).where(RefreshToken.jti_hash == jti_hash))
            if token is not None and token.revoked_at is None: token.revoked_at = datetime.now(timezone.utc)


class SqlChatRepository:
    def __init__(self, database: Database) -> None: self.database = database
    def create_session(self, session_id: str, user_id: str, message: str) -> ChatSession:
        item = ChatSession(id=session_id, user_id=user_id, title=message[:200], status="queued", events=[])
        item.messages.append(ChatMessage(id=uuid4().hex, role="user", content=message))
        with self.database.session() as session: session.add(item)
        return item
    def append_user_message(self, session_id: str, message: str) -> None:
        with self.database.session() as session:
            item = session.get(ChatSession, session_id)
            if item is None: return
            item.messages.append(ChatMessage(id=uuid4().hex, role="user", content=message))
            item.updated_at = datetime.now(timezone.utc)
    def create_run(self, run_id: str, session_id: str) -> ChatRun:
        item = ChatRun(id=run_id, session_id=session_id, status="queued", events=[])
        with self.database.session() as session: session.add(item)
        return item
    def update_run(self, run_id: str, **updates) -> None:
        with self.database.session() as session:
            item = session.get(ChatRun, run_id)
            if item is None: return
            for key, value in updates.items(): setattr(item, key, value)
            item.updated_at = datetime.now(timezone.utc)
    def update_session(self, session_id: str, **updates) -> None:
        with self.database.session() as session:
            item = session.get(ChatSession, session_id)
            if item is None: return
            for key, value in updates.items(): setattr(item, key, value)
            item.updated_at = datetime.now(timezone.utc)
    def append_event(self, run_id: str, event: dict, status: str | None = None) -> None:
        with self.database.session() as session:
            item = session.get(ChatRun, run_id)
            if item is None: return
            item.events = [*(item.events or []), event]
            if status is not None: item.status = status
            item.heartbeat_at = datetime.now(timezone.utc)
            item.updated_at = item.heartbeat_at
    def complete_run(self, run_id: str, answer: str, finished_at: datetime) -> None:
        with self.database.session() as session:
            run = session.scalar(select(ChatRun).options(selectinload(ChatRun.session)).where(ChatRun.id == run_id))
            if run is None: return
            run.status, run.answer, run.error = "completed", answer, None
            run.heartbeat_at = run.finished_at = run.updated_at = finished_at
            run.session.status, run.session.answer, run.session.error = "completed", answer, None
            run.session.finished_at = run.session.updated_at = finished_at
            run.session.messages.append(ChatMessage(id=uuid4().hex, role="assistant", content=answer))
    def get_run(self, run_id: str) -> ChatRun | None:
        with self.database.session() as session:
            return session.scalar(select(ChatRun).options(selectinload(ChatRun.session)).where(ChatRun.id == run_id))
    def get(self, session_id: str) -> ChatSession | None:
        with self.database.session() as session:
            return session.scalar(select(ChatSession).options(selectinload(ChatSession.messages)).where(ChatSession.id == session_id))
    def list(self, user_id: str | None, limit: int = 20) -> list[ChatSession]:
        statement = select(ChatSession).options(selectinload(ChatSession.messages)).order_by(ChatSession.updated_at.desc())
        if user_id is not None: statement = statement.where(ChatSession.user_id == user_id)
        with self.database.session() as session: return list(session.scalars(statement.limit(limit)))
    def fail_stale(self, cutoff: datetime, finished_at: datetime) -> int:
        count = 0
        with self.database.session() as session:
            items = session.scalars(select(ChatRun).where(ChatRun.status.in_(["processing", "retrying"]), ChatRun.heartbeat_at.is_not(None), ChatRun.heartbeat_at < cutoff))
            for item in items:
                item.status, item.error, item.finished_at = "failed", "Worker heartbeat timed out.", finished_at
                item.session.status, item.session.error, item.session.finished_at = item.status, item.error, finished_at
                count += 1
        return count


class SqlKnowledgeBaseRepository:
    def __init__(self, database: Database) -> None: self.database = database
    def get_version(self, user_id: str) -> int:
        with self.database.session() as session:
            version = session.scalar(select(User.knowledge_base_version).where(User.id == user_id))
            return int(version or 1)
    def bump_version(self, user_id: str) -> int:
        statement = update(User).where(User.id == user_id).values(knowledge_base_version=User.knowledge_base_version + 1).returning(User.knowledge_base_version)
        with self.database.session() as session:
            version = session.scalar(statement)
            if version is None: raise ValueError("Cannot version a knowledge base for an unknown user.")
            return int(version)


class SqlUploadRepository:
    def __init__(self, database: Database) -> None: self.database = database
    def create(self, job_id: str, user_id: str, file_name: str, message: str, content_type: str | None = None, size_bytes: int | None = None) -> UploadJob:
        item = UploadJob(id=job_id, user_id=user_id, file_name=file_name, message=message, content_type=content_type, size_bytes=size_bytes)
        with self.database.session() as session: session.add(item)
        return item
    def update(self, job_id: str, **updates) -> None:
        with self.database.session() as session:
            item = session.get(UploadJob, job_id)
            if item is None: return
            for key, value in updates.items():
                if hasattr(item, key): setattr(item, key, value)
            item.updated_at = datetime.now(timezone.utc)
    def claim_retry(self, job_id: str, user_id: str | None = None) -> bool:
        now = datetime.now(timezone.utc)
        statement = (
            update(UploadJob)
            .where(UploadJob.id == job_id, UploadJob.status == "failed")
            .values(
                status="queued",
                phase="queued",
                message="Upload retry queued.",
                progress=1,
                task_id=None,
                worker_id=None,
                heartbeat_at=None,
                started_at=None,
                finished_at=None,
                error=None,
                raw_path=None,
                processed_path=None,
                metadata_path=None,
                processed_object_key=None,
                metadata_object_key=None,
                chunk_count=None,
                indexed_chunks=0,
                total_chunks=None,
                source_name=None,
                updated_at=now,
            )
        )
        if user_id is not None:
            statement = statement.where(UploadJob.user_id == user_id)
        with self.database.session() as session:
            return bool(session.execute(statement).rowcount)
    def get(self, job_id: str) -> UploadJob | None:
        with self.database.session() as session: return session.get(UploadJob, job_id)
    def list(self, user_id: str | None, limit: int = 20) -> list[UploadJob]:
        statement = select(UploadJob).order_by(UploadJob.updated_at.desc())
        if user_id is not None: statement = statement.where(UploadJob.user_id == user_id)
        with self.database.session() as session: return list(session.scalars(statement.limit(limit)))
    def fail_stale(self, cutoff: datetime, finished_at: datetime) -> int:
        count = 0
        with self.database.session() as session:
            items = session.scalars(select(UploadJob).where(UploadJob.status.in_(["processing", "retrying"]), UploadJob.heartbeat_at.is_not(None), UploadJob.heartbeat_at < cutoff))
            for item in items:
                item.status, item.phase, item.message = "failed", "stale", "Worker heartbeat timed out."
                item.error, item.finished_at = "Background task stopped reporting progress.", finished_at
                count += 1
        return count


class SqlDocumentRepository:
    def __init__(self, database: Database) -> None: self.database = database
    def upsert_from_upload(self, job: UploadJob) -> None:
        if not job.processed_path: return
        with self.database.session() as session:
            item = session.scalar(select(Document).where(Document.user_id == job.user_id, Document.source == job.processed_path))
            item = item or Document(id=uuid4().hex, user_id=job.user_id, upload_job_id=job.id, source=job.processed_path, file_name=job.file_name)
            item.raw_path, item.metadata_path, item.chunk_count = job.raw_path, job.metadata_path, job.chunk_count or 0
            item.updated_at = datetime.now(timezone.utc)
            session.add(item)
    def delete_by_source(self, user_id: str, source: str) -> bool:
        statement = delete(Document).where(Document.user_id == user_id, Document.source == source)
        with self.database.session() as session:
            result = session.execute(statement)
            return bool(result.rowcount)


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
