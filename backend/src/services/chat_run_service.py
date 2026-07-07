from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor

from backend.src.monitoring import agent_run_monitor
from backend.src.services.chat_service import ChatService

logger = logging.getLogger(__name__)


class ChatRunService:
    def __init__(self, chat_service: ChatService | None = None, max_workers: int = 2) -> None:
        self._chat_service = chat_service or ChatService()
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="chat-worker")

    def create_chat_run(self, message: str) -> dict:
        run = agent_run_monitor.create_run("chat", message)
        self._executor.submit(self._run_chat_job, run["run_id"], message)
        return run

    def get_chat_run(self, run_id: str) -> dict | None:
        return agent_run_monitor.get_run(run_id)

    def _run_chat_job(self, run_id: str, message: str) -> None:
        agent_run_monitor.update_run(run_id, status="processing", message="Starting agent run.")
        with agent_run_monitor.bind_run(run_id):
            agent_run_monitor.append_event(
                "chat_received",
                "Received chat message and started agent workflow.",
                {"message_length": len(message)},
                status="processing",
            )
            try:
                answer = self._chat_service.answer(message)
                agent_run_monitor.append_event(
                    "chat_completed",
                    "Final answer generated.",
                    {"answer_length": len(answer)},
                    status="processing",
                )
                agent_run_monitor.complete_run(run_id, answer)
            except Exception as exc:
                logger.exception("[chat/run_service] Chat run failed: run_id=%s", run_id)
                agent_run_monitor.append_event(
                    "chat_failed",
                    "Agent workflow failed.",
                    {"error": str(exc)},
                    status="failed",
                )
                agent_run_monitor.fail_run(run_id, str(exc))
