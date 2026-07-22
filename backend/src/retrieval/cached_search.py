from __future__ import annotations

import re
import unicodedata
import logging
from dataclasses import dataclass
from typing import Protocol

from backend.src.core.repositories import KnowledgeBaseRepository
from backend.src.monitoring import agent_run_monitor
from backend.src.retrieval.reranker import IdentityReranker, Reranker

logger = logging.getLogger(__name__)


class RetrievalCache(Protocol):
    def get_exact(self, owner_id: str, version: int, normalized_query: str) -> list[dict] | None: ...
    def get_semantic(self, owner_id: str, version: int, embedding: list[float]) -> list[dict] | None: ...
    def put(self, owner_id: str, version: int, normalized_query: str, embedding: list[float], results: list[dict]) -> None: ...


class GraphSearcher(Protocol):
    def search(self, query: str, owner_id: str | None = None, query_embedding: list[float] | None = None) -> list[dict]: ...


@dataclass(frozen=True)
class RetrievalOutcome:
    query: str
    normalized_query: str
    owner_id: str
    knowledge_base_version: int
    cache_status: str
    reranker_model: str
    results: list[dict]


class CachedGraphSearcher:
    def __init__(
        self,
        searcher: GraphSearcher,
        cache: RetrievalCache,
        knowledge_bases: KnowledgeBaseRepository,
        embeddings_factory,
        reranker: Reranker | None = None,
    ) -> None:
        self._searcher = searcher
        self._cache = cache
        self._knowledge_bases = knowledge_bases
        self._embeddings_factory = embeddings_factory
        self._reranker = reranker or IdentityReranker()

    def search(self, query: str, owner_id: str) -> list[dict]:
        return self.search_with_artifact(query, owner_id).results

    def search_with_artifact(self, query: str, owner_id: str) -> RetrievalOutcome:
        normalized_query = normalize_query(query)
        version = self._knowledge_bases.get_version(owner_id)
        exact = self._cache.get_exact(owner_id, version, normalized_query)
        if exact is not None:
            ranked = self._rerank(query, exact, version)
            self._cache_event("exact_cache_hit", version, len(ranked))
            return self._outcome(query, normalized_query, owner_id, version, "exact_hit", ranked)

        agent_run_monitor.append_event("embed_query", "Generating the query embedding for retrieval cache lookup.", status="processing")
        embedding = self._embeddings_factory().embed_query(query)
        semantic = self._cache.get_semantic(owner_id, version, embedding)
        if semantic is not None:
            ranked = self._rerank(query, semantic, version)
            self._cache_event("semantic_cache_hit", version, len(ranked))
            return self._outcome(query, normalized_query, owner_id, version, "semantic_hit", ranked)

        self._cache_event("retrieval_cache_miss", version, 0)
        results = self._searcher.search(query, owner_id=owner_id, query_embedding=embedding)
        ranked = self._rerank(query, results, version)
        self._cache.put(owner_id, version, normalized_query, embedding, ranked)
        return self._outcome(query, normalized_query, owner_id, version, "miss", ranked)

    def _rerank(self, query: str, results: list[dict], version: int) -> list[dict]:
        if not results:
            return []
        agent_run_monitor.append_event(
            "rerank_start",
            "Re-ranking retrieved candidates with a cross-encoder.",
            {"candidate_count": len(results), "model": self._reranker.model_name, "knowledge_base_version": version},
            status="processing",
        )
        try:
            ranked = self._reranker.rerank(query, results)
        except Exception:
            logger.exception("Cross-encoder reranking failed; returning first-stage retrieval candidates")
            agent_run_monitor.append_event(
                "rerank_failed",
                "Cross-encoder re-ranking was unavailable; using first-stage retrieval order.",
                {"candidate_count": len(results), "model": self._reranker.model_name, "knowledge_base_version": version},
                status="processing",
            )
            return results
        agent_run_monitor.append_event(
            "rerank_complete",
            "Cross-encoder re-ranking completed.",
            {"result_count": len(ranked), "model": self._reranker.model_name, "knowledge_base_version": version},
            status="processing",
        )
        return ranked

    def _outcome(
        self,
        query: str,
        normalized_query: str,
        owner_id: str,
        version: int,
        cache_status: str,
        results: list[dict],
    ) -> RetrievalOutcome:
        return RetrievalOutcome(
            query=query,
            normalized_query=normalized_query,
            owner_id=owner_id,
            knowledge_base_version=version,
            cache_status=cache_status,
            reranker_model=self._reranker.model_name,
            results=results,
        )

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
