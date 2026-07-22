from __future__ import annotations

import os
import logging

from redis import Redis
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)


class ChatTokenStreamPublisher:
    def __init__(self, client: Redis | None = None, ttl_seconds: int | None = None) -> None:
        self._client = client or Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"), decode_responses=True)
        self._ttl = ttl_seconds or int(os.getenv("CHAT_TOKEN_STREAM_TTL_SECONDS", "3600"))
        self._max_events = int(os.getenv("CHAT_TOKEN_STREAM_MAX_EVENTS", "10000"))

    def start(self, run_id: str, attempt: int) -> None:
        self._append(run_id, {"type": "start", "attempt": str(attempt)})

    def token(self, run_id: str, content: str) -> None:
        if content:
            self._append(run_id, {"type": "token", "content": content})

    def status(self, run_id: str, status: str, message: str) -> None:
        self._append(run_id, {"type": "status", "status": status, "message": message})

    def complete(self, run_id: str) -> None:
        self._append(run_id, {"type": "done"})

    def error(self, run_id: str, message: str) -> None:
        self._append(run_id, {"type": "error", "message": message})

    def _append(self, run_id: str, fields: dict[str, str]) -> None:
        key = token_stream_key(run_id)
        try:
            pipeline = self._client.pipeline()
            pipeline.xadd(key, fields, maxlen=self._max_events, approximate=True)
            pipeline.expire(key, self._ttl)
            pipeline.execute()
        except RedisError:
            logger.warning("Could not publish chat token stream event: run_id=%s type=%s", run_id, fields.get("type"), exc_info=True)


def token_stream_key(run_id: str) -> str:
    return f"chat:tokens:{run_id}"
