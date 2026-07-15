from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from array import array
from typing import Any

from redis import Redis
from redis.commands.search.field import NumericField, TagField, VectorField
from redis.commands.search.index_definition import IndexDefinition, IndexType
from redis.commands.search.query import Query
from redis.exceptions import RedisError, ResponseError

logger = logging.getLogger(__name__)


class RedisRetrievalCache:
    def __init__(
        self,
        client: Redis | None = None,
        ttl_seconds: int | None = None,
        max_entries: int | None = None,
        similarity_threshold: float | None = None,
        embedding_model: str | None = None,
        embedding_dimensions: int | None = None,
    ) -> None:
        self._client = client or Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
        self._ttl = ttl_seconds or int(os.getenv("RETRIEVAL_CACHE_TTL_SECONDS", "300"))
        self._max_entries = max_entries or int(os.getenv("RETRIEVAL_CACHE_MAX_ENTRIES", "100"))
        self._threshold = similarity_threshold or float(os.getenv("RETRIEVAL_CACHE_SIMILARITY_THRESHOLD", "0.93"))
        model = embedding_model or os.getenv("EMBEDDING_MODEL_NAME", "unknown")
        self._dimensions = embedding_dimensions or int(os.getenv("EMBEDDING_DIMENSIONS", "768"))
        self._space = hashlib.sha256(f"{model}:{self._dimensions}".encode()).hexdigest()[:12]
        self._prefix = f"ragcache:item:{self._space}:"
        self._index_name = f"ragcache_idx_{self._space}"
        self._index_ready = False

    def get_exact(self, owner_id: str, version: int, normalized_query: str) -> list[dict] | None:
        key = self._item_key(owner_id, version, normalized_query)
        try:
            payload = self._client.hget(key, "results")
            if payload is None:
                return None
            self._touch(owner_id, version, key)
            return json.loads(payload)
        except (RedisError, ValueError, TypeError):
            logger.warning("Exact retrieval cache lookup failed", exc_info=True)
            return None

    def get_semantic(self, owner_id: str, version: int, embedding: list[float]) -> list[dict] | None:
        if len(embedding) != self._dimensions:
            logger.warning("Skipping semantic cache: expected %s dimensions, received %s", self._dimensions, len(embedding))
            return None
        try:
            self._ensure_index()
            query = (
                Query(f"(@owner_id:{{{owner_id}}} @kb_version:[{version} {version}])=>[KNN 1 @embedding $vector AS distance]")
                .sort_by("distance")
                .return_fields("results", "distance")
                .paging(0, 1)
                .dialect(2)
            )
            response = self._client.ft(self._index_name).search(
                query,
                query_params={"vector": self._vector_bytes(embedding)},
            )
            if not response.docs:
                return None
            document = response.docs[0]
            similarity = 1.0 - float(document.distance)
            if similarity < self._threshold:
                return None
            key = str(document.id)
            self._touch(owner_id, version, key)
            return json.loads(document.results)
        except (RedisError, ValueError, TypeError, AttributeError):
            logger.warning("Semantic retrieval cache lookup failed", exc_info=True)
            return None

    def put(self, owner_id: str, version: int, normalized_query: str, embedding: list[float], results: list[dict]) -> None:
        if not results or len(embedding) != self._dimensions:
            return
        key = self._item_key(owner_id, version, normalized_query)
        try:
            self._ensure_index()
            pipeline = self._client.pipeline()
            pipeline.hset(
                key,
                mapping={
                    "owner_id": owner_id,
                    "kb_version": version,
                    "query": normalized_query,
                    "embedding": self._vector_bytes(embedding),
                    "results": json.dumps(results, ensure_ascii=True),
                },
            )
            pipeline.expire(key, self._ttl)
            pipeline.execute()
            self._touch(owner_id, version, key)
            self._prune(owner_id, version)
        except (RedisError, ValueError, TypeError):
            logger.warning("Could not write retrieval cache entry", exc_info=True)

    def _ensure_index(self) -> None:
        if self._index_ready:
            return
        schema = (
            TagField("owner_id"),
            NumericField("kb_version"),
            VectorField(
                "embedding",
                "HNSW",
                {"TYPE": "FLOAT32", "DIM": self._dimensions, "DISTANCE_METRIC": "COSINE"},
            ),
        )
        try:
            self._client.ft(self._index_name).create_index(
                schema,
                definition=IndexDefinition(prefix=[self._prefix], index_type=IndexType.HASH),
            )
        except ResponseError as exc:
            if "Index already exists" not in str(exc):
                raise
        self._index_ready = True

    def _touch(self, owner_id: str, version: int, key: str) -> None:
        lru_key = self._lru_key(owner_id, version)
        pipeline = self._client.pipeline()
        pipeline.expire(key, self._ttl)
        pipeline.zadd(lru_key, {key: time.time()})
        pipeline.expire(lru_key, self._ttl)
        pipeline.execute()

    def _prune(self, owner_id: str, version: int) -> None:
        lru_key = self._lru_key(owner_id, version)
        count = self._client.zcard(lru_key)
        excess = count - self._max_entries
        if excess <= 0:
            return
        stale_keys = self._client.zrange(lru_key, 0, excess - 1)
        if stale_keys:
            pipeline = self._client.pipeline()
            pipeline.delete(*stale_keys)
            pipeline.zrem(lru_key, *stale_keys)
            pipeline.execute()

    def _item_key(self, owner_id: str, version: int, normalized_query: str) -> str:
        digest = hashlib.sha256(f"{owner_id}:{version}:{normalized_query}".encode()).hexdigest()
        return f"{self._prefix}{digest}"

    def _lru_key(self, owner_id: str, version: int) -> str:
        return f"ragcache:lru:{self._space}:{owner_id}:{version}"

    @staticmethod
    def _vector_bytes(embedding: list[float]) -> bytes:
        return array("f", embedding).tobytes()
