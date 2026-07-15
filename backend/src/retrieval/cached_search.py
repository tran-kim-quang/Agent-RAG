from __future__ import annotations

import re
import unicodedata
from typing import Protocol

from backend.src.core.repositories import KnowledgeBaseRepository
from backend.src.monitoring import agent_run_monitor


class RetrievalCache(Protocol):
    def get_exact(self, owner_id: str, version: int, normalized_query: str) -> list[dict] | None: ...
    def get_semantic(self, owner_id: str, version: int, embedding: list[float]) -> list[dict] | None: ...
    def put(self, owner_id: str, version: int, normalized_query: str, embedding: list[float], results: list[dict]) -> None: ...


class GraphSearcher(Protocol):
    def search(self, query: str, owner_id: str | None = None, query_embedding: list[float] | None = None) -> list[dict]: ...


class CachedGraphSearcher:
    def __init__(self, searcher: GraphSearcher, cache: RetrievalCache, knowledge_bases: KnowledgeBaseRepository, embeddings_factory) -> None:
        self._searcher = searcher
        self._cache = cache
        self._knowledge_bases = knowledge_bases
        self._embeddings_factory = embeddings_factory

    def search(self, query: str, owner_id: str) -> list[dict]:
        normalized_query = normalize_query(query)
        version = self._knowledge_bases.get_version(owner_id)
        exact = self._cache.get_exact(owner_id, version, normalized_query)
        if exact is not None:
            self._cache_event("exact_cache_hit", version, len(exact))
            return exact

        agent_run_monitor.append_event("embed_query", "Generating the query embedding for retrieval cache lookup.", status="processing")
        embedding = self._embeddings_factory().embed_query(query)
        semantic = self._cache.get_semantic(owner_id, version, embedding)
        if semantic is not None:
            self._cache_event("semantic_cache_hit", version, len(semantic))
            return semantic

        self._cache_event("retrieval_cache_miss", version, 0)
        results = self._searcher.search(query, owner_id=owner_id, query_embedding=embedding)
        self._cache.put(owner_id, version, normalized_query, embedding, results)
        return results

    @staticmethod
    def _cache_event(phase: str, version: int, result_count: int) -> None:
        agent_run_monitor.append_event(
            phase,
            phase.replace("_", " ").capitalize() + ".",
            {"knowledge_base_version": version, "result_count": result_count},
            status="processing",
        )


def normalize_query(query: str) -> str:
    normalized = unicodedata.normalize("NFKC", query).casefold().strip()
    return re.sub(r"\s+", " ", normalized)
