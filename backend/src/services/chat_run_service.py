from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable
from uuid import uuid4

from backend.src.core.repositories import ChatRepository
from backend.src.db import ChatRun, ChatSession


class ChatRunService:
    def __init__(self, chats: ChatRepository, enqueue: Callable[[str, str, str, str], str] | None = None) -> None:
        self._chats = chats
        self._enqueue = enqueue or self._enqueue_task

    def create_chat_run(self, message: str, user_id: str, chat_session_id: str | None = None) -> dict:
        if chat_session_id is None:
            chat_session_id = uuid4().hex
            self._chats.create_session(chat_session_id, user_id, message)
        else:
            session = self._chats.get(chat_session_id)
            if session is None or session.user_id != user_id:
                raise PermissionError("Chat session not found.")
            if session.status in {"queued", "processing", "retrying"}:
                raise RuntimeError("This chat session already has an active run.")
            self._chats.append_user_message(chat_session_id, message)

        run_id = uuid4().hex
        self._chats.create_run(run_id, chat_session_id)
        self._chats.update_session(chat_session_id, status="queued", answer=None, error=None, events=[], finished_at=None)
        try:
            task_id = self._enqueue(run_id, chat_session_id, user_id, message)
            self._chats.update_run(run_id, task_id=task_id)
            self._chats.update_session(chat_session_id, task_id=task_id)
        except Exception as exc:
            self._chats.update_run(
                run_id,
                status="failed",
                error=f"Could not enqueue chat task: {exc}",
                finished_at=datetime.now(timezone.utc),
            )
            self._chats.update_session(chat_session_id, status="failed", error=f"Could not enqueue chat task: {exc}")
            raise
        return {
            "run_id": run_id,
            "chat_session_id": chat_session_id,
            "status": "queued",
            "message": "Queued agent run.",
            "answer": None,
            "error": None,
            "events": [],
        }

    def get_chat_run(self, run_id: str, user_id: str, is_admin: bool = False) -> dict | None:
        item = self._chats.get_run(run_id)
        if item is None or (not is_admin and item.session.user_id != user_id):
            return None
        return self._session_to_run(item)

    def list_chat_sessions(self, user_id: str | None, limit: int = 20) -> list[ChatSession]:
        return self._chats.list(user_id=user_id, limit=limit)

    @staticmethod
    def _enqueue_task(run_id: str, chat_session_id: str, user_id: str, message: str) -> str:
        from backend.src.tasks.jobs import run_chat_task

        return run_chat_task.apply_async(args=[run_id, chat_session_id, user_id, message]).id

    @staticmethod
    def _session_to_run(item: ChatRun) -> dict:
        latest_event = (item.events or [])[-1] if item.events else None
        return {
            "run_id": item.id,
            "chat_session_id": item.session_id,
            "status": item.status,
            "message": latest_event["message"] if latest_event else f"Agent run is {item.status}.",
            "answer": item.answer,
            "error": item.error,
            "events": item.events or [],
        }
