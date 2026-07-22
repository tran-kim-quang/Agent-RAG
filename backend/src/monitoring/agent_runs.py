from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from threading import Lock
from uuid import uuid4


_CURRENT_RUN_ID: ContextVar[str | None] = ContextVar("current_agent_run_id", default=None)
_CURRENT_EVENT_SINK: ContextVar[object | None] = ContextVar("current_agent_event_sink", default=None)


class AgentRunMonitor:
    def __init__(self) -> None:
        self._lock = Lock()
        self._runs: dict[str, dict] = {}

    def create_run(self, run_type: str, input_text: str, user_id: str | None = None) -> dict:
        timestamp = self._now_iso()
        run = {
            "run_id": uuid4().hex,
            "type": run_type,
            "status": "queued",
            "message": "Queued agent run.",
            "input": input_text,
            "user_id": user_id,
            "answer": None,
            "error": None,
            "events": [],
            "created_at": timestamp,
            "updated_at": timestamp,
        }
        with self._lock:
            self._runs[run["run_id"]] = run
        return dict(run)

    def get_run(self, run_id: str) -> dict | None:
        with self._lock:
            run = self._runs.get(run_id)
            if run is None:
                return None
            return self._copy_run(run)

    def list_runs(self, limit: int = 20) -> list[dict]:
        with self._lock:
            runs = sorted(
                self._runs.values(),
                key=lambda run: run.get("updated_at", ""),
                reverse=True,
            )
            return [self._copy_run(run) for run in runs[:limit]]

    def update_run(self, run_id: str, **updates) -> None:
        with self._lock:
            run = self._runs[run_id]
            run.update(updates)
            run["updated_at"] = self._now_iso()

    def append_event(
        self,
        phase: str,
        message: str,
        details: dict | None = None,
        *,
        status: str | None = None,
        run_id: str | None = None,
    ) -> None:
        target_run_id = run_id or _CURRENT_RUN_ID.get()
        if not target_run_id:
            return

        event = {
            "timestamp": self._now_iso(),
            "phase": phase,
            "message": message,
            "details": details or {},
        }
        with self._lock:
            run = self._runs.get(target_run_id)
            if run is not None:
                run["events"].append(event)
                run["message"] = message
                if status is not None:
                    run["status"] = status
                run["updated_at"] = event["timestamp"]
        sink = _CURRENT_EVENT_SINK.get()
        if sink is not None:
            sink(event, status)

    def complete_run(self, run_id: str, answer: str) -> None:
        self.update_run(
            run_id,
            status="completed",
            message="Agent run completed.",
            answer=answer,
            error=None,
        )

    def fail_run(self, run_id: str, error: str) -> None:
        self.update_run(
            run_id,
            status="failed",
            message="Agent run failed.",
            error=error,
        )

    @contextmanager
    def bind_run(self, run_id: str):
        token = _CURRENT_RUN_ID.set(run_id)
        try:
            yield
        finally:
            _CURRENT_RUN_ID.reset(token)

    @contextmanager
    def bind_event_sink(self, sink):
        token = _CURRENT_EVENT_SINK.set(sink)
        try:
            yield
        finally:
            _CURRENT_EVENT_SINK.reset(token)

    @staticmethod
    def _copy_run(run: dict) -> dict:
        copied = dict(run)
        copied["events"] = [dict(event) for event in run.get("events", [])]
        return copied

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()


agent_run_monitor = AgentRunMonitor()
