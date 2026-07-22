from __future__ import annotations

import logging
import os

from fastapi import HTTPException, Request
from redis import Redis
from redis.backoff import NoBackoff
from redis.exceptions import RedisError
from redis.retry import Retry

logger = logging.getLogger(__name__)
client = Redis.from_url(
    os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    decode_responses=True,
    socket_connect_timeout=0.2,
    socket_timeout=0.2,
    retry=Retry(NoBackoff(), 0),
)


def enforce_rate_limit(request: Request, scope: str, identifier: str, limit: int, window_seconds: int) -> None:
    key = f"rate:{scope}:{identifier}"
    try:
        with client.pipeline() as pipeline:
            pipeline.incr(key)
            pipeline.expire(key, window_seconds, nx=True)
            count, _ = pipeline.execute()
    except RedisError:
        logger.warning("Rate limiter unavailable for scope=%s", scope)
        if os.getenv("ENVIRONMENT", "development").lower() == "production":
            raise HTTPException(status_code=503, detail="Request protection service is unavailable.")
        return
    if int(count) > limit:
        raise HTTPException(status_code=429, detail="Too many requests. Try again later.")


def client_identifier(request: Request) -> str:
    return request.client.host if request.client else "unknown"
