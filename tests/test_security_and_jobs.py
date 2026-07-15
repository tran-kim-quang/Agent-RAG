from __future__ import annotations

from pathlib import Path

import pytest

from backend.src.db import Database, SqlChatRepository, SqlKnowledgeBaseRepository, SqlRefreshTokenRepository, SqlUploadRepository, SqlUserRepository
from backend.src.security import AuthService, TokenError
from backend.src.services import ChatRunService, UploadJobService


class FakeObjectStorage:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def put_bytes(self, object_key: str, content: bytes, content_type: str) -> str:
        self.objects[object_key] = content
        return object_key

    def get_bytes(self, object_key: str) -> bytes:
        return self.objects[object_key]


@pytest.fixture
def database(tmp_path: Path) -> Database:
    database = Database(f"sqlite:///{tmp_path / 'app.db'}")
    database.create_schema()
    return database


def test_refresh_tokens_are_rotated_and_single_use(database: Database, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET", "test-secret-that-is-long-enough-for-tests")
    monkeypatch.setenv("ALLOW_FIRST_USER_ADMIN", "false")
    auth = AuthService(SqlUserRepository(database), SqlRefreshTokenRepository(database))
    user = auth.register("user@example.com", "password1234")

    pair = auth.issue_token_pair(user)
    rotated = auth.rotate_refresh_token(pair.refresh_token)

    assert auth.decode_access_token(rotated.access_token).id == user.id
    with pytest.raises(TokenError):
        auth.rotate_refresh_token(pair.refresh_token)


def test_chat_service_enqueues_and_enforces_ownership(database: Database) -> None:
    users = SqlUserRepository(database)
    owner = users.create("owner@example.com", "hash")
    stranger = users.create("stranger@example.com", "hash")
    queued: list[tuple[str, str, str, str]] = []
    service = ChatRunService(SqlChatRepository(database), enqueue=lambda run_id, session_id, user_id, message: queued.append((run_id, session_id, user_id, message)) or "task-1")

    run = service.create_chat_run("private question", owner.id)

    assert queued == [(run["run_id"], run["chat_session_id"], owner.id, "private question")]
    assert service.get_chat_run(run["run_id"], owner.id) is not None
    assert service.get_chat_run(run["run_id"], stranger.id) is None

    service._chats.update_session(run["chat_session_id"], status="completed")
    follow_up = service.create_chat_run("follow-up question", owner.id, run["chat_session_id"])

    assert follow_up["chat_session_id"] == run["chat_session_id"]
    assert [message.content for message in service._chats.get(run["chat_session_id"]).messages] == ["private question", "follow-up question"]
    with pytest.raises(PermissionError):
        service.create_chat_run("unauthorized", stranger.id, run["chat_session_id"])


def test_knowledge_base_version_increments_atomically(database: Database) -> None:
    user = SqlUserRepository(database).create("versioned@example.com", "hash")
    versions = SqlKnowledgeBaseRepository(database)

    assert versions.get_version(user.id) == 1
    assert versions.bump_version(user.id) == 2
    assert versions.get_version(user.id) == 2


def test_upload_is_stored_before_enqueue_and_enforces_ownership(database: Database) -> None:
    users = SqlUserRepository(database)
    owner = users.create("owner@example.com", "hash")
    stranger = users.create("stranger@example.com", "hash")
    storage = FakeObjectStorage()
    queued: list[tuple[str, str, str, str]] = []
    service = UploadJobService(
        SqlUploadRepository(database),
        storage,  # type: ignore[arg-type]
        enqueue=lambda job_id, user_id, name, key: queued.append((job_id, user_id, name, key)) or "task-2",
    )

    job = service.create_upload_job("../contract.pdf", b"pdf-content", owner.id, "application/pdf")

    assert job["file_name"] == "contract.pdf"
    assert storage.objects[job["raw_object_key"]] == b"pdf-content"
    assert queued[0][3] == job["raw_object_key"]
    assert service.get_upload_job(job["job_id"], owner.id) is not None
    assert service.get_upload_job(job["job_id"], stranger.id) is None
