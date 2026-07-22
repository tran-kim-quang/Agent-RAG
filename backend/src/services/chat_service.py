from __future__ import annotations

import logging
from typing import Callable

from backend.src.monitoring import agent_run_monitor

logger = logging.getLogger(__name__)


class ChatService:
    def __init__(self, query_runner: Callable[[str, str, list[dict[str, str]]], str] | None = None) -> None:
        self._query_runner = query_runner

    def answer(
        self,
        message: str,
        chat_session_id: str,
        history: list[dict[str, str]],
        token_callback: Callable[[str], None] | None = None,
    ) -> str:
        logger.info("[chat/service] Handling chat request")
        agent_run_monitor.append_event(
            "chat_service_start",
            "Chat service is preparing the orchestrator request.",
            {"message_length": len(message)},
            status="processing",
        )
        query_runner = self._query_runner or self._default_query_runner
        if self._query_runner is None:
            answer = self._default_query_runner(message, chat_session_id, history, token_callback)
        else:
            answer = query_runner(message, chat_session_id, history)
        agent_run_monitor.append_event(
            "chat_service_complete",
            "Chat service received the orchestrator answer.",
            {"answer_length": len(answer)},
            status="processing",
        )
        logger.info("[chat/service] Chat request completed")
        return answer

    @staticmethod
    def _default_query_runner(
        message: str,
        chat_session_id: str,
        history: list[dict[str, str]],
        token_callback: Callable[[str], None] | None = None,
    ) -> str:
        from backend.src.agents.orchestrator import run as run_query

        return run_query(message, chat_session_id, history, token_callback=token_callback)
