from functools import lru_cache
from typing import Callable

from langchain_community.embeddings import OllamaEmbeddings

from backend.src.monitoring import agent_run_monitor
from backend.src.security import current_user_id
from backend.src.infrastructure import create_neo4j_driver, get_ollama_embeddings, load_config
from backend.src.infrastructure.retrieval_cache import RedisRetrievalCache
from backend.src.db import Database, SqlKnowledgeBaseRepository
from backend.src.retrieval.cached_search import CachedGraphSearcher

_CFG = load_config()["retriever"]

TOP_K: int = _CFG["top_k"]
GRAPH_MAX_HOPS: int = _CFG["graph_max_hops"]
RRF_K: int = _CFG["rrf_k"]


class Neo4jGraphSearcher:
    def __init__(
        self,
        embeddings_factory: Callable[[], OllamaEmbeddings] = get_ollama_embeddings,
        driver_factory: Callable[[], object] = create_neo4j_driver,
        top_k: int = TOP_K,
        max_hops: int = GRAPH_MAX_HOPS,
        rrf_k: int = RRF_K,
    ) -> None:
        self._embeddings_factory = embeddings_factory
        self._driver_factory = driver_factory
        self._top_k = top_k
        self._max_hops = max_hops
        self._rrf_k = rrf_k

    def search(self, query: str, owner_id: str | None = None, query_embedding: list[float] | None = None) -> list[dict]:
        owner_id = owner_id or current_user_id()
        if owner_id is None:
            return []
        if query_embedding is None:
            agent_run_monitor.append_event("embed_query", "Generating the query embedding for semantic retrieval.", status="processing")
            query_embedding = self._embeddings_factory().embed_query(query)

        driver = self._driver_factory()
        with driver.session() as session:
            agent_run_monitor.append_event(
                "vector_search",
                "Searching top matching chunks in the Neo4j vector index.",
                {"top_k": self._top_k},
                status="processing",
            )
            seed_result = session.run(
                """
                CALL db.index.vector.queryNodes('document_chunks', $candidate_k, $embedding)
                YIELD node AS chunk, score
                WHERE chunk.owner_id = $owner_id
                RETURN
                    elementId(chunk)   AS id,
                    chunk.text         AS text,
                    chunk.source       AS source,
                    chunk.chunk_index  AS chunk_index,
                    score
                ORDER BY score DESC
                LIMIT $top_k
                """,
                top_k=self._top_k,
                candidate_k=max(self._top_k * 10, 100),
                embedding=query_embedding,
                owner_id=owner_id,
            )
            seeds = [dict(record) for record in seed_result]

            if not seeds:
                agent_run_monitor.append_event(
                    "vector_search_complete",
                    "Vector search returned no seed chunks.",
                    {"seed_count": 0},
                    status="processing",
                )
                driver.close()
                return []

            seed_ids = [seed["id"] for seed in seeds]
            agent_run_monitor.append_event(
                "graph_expand",
                "Expanding neighboring chunks through NEXT_CHUNK relationships.",
                {"seed_count": len(seeds), "max_hops": self._max_hops},
                status="processing",
            )
            neighbour_result = session.run(
                f"""
                UNWIND $seed_ids AS seedId
                MATCH (seed)
                WHERE elementId(seed) = seedId
                MATCH path = (seed)-[:NEXT_CHUNK*1..{self._max_hops}]-(neighbour:Chunk)
                WHERE neighbour.owner_id = $owner_id
                RETURN DISTINCT
                    elementId(neighbour) AS id,
                    neighbour.text        AS text,
                    neighbour.source      AS source,
                    neighbour.chunk_index AS chunk_index
                """,
                seed_ids=seed_ids,
                owner_id=owner_id,
            )
            neighbours = [dict(record) for record in neighbour_result]

        driver.close()
        agent_run_monitor.append_event(
            "rerank",
            "Re-ranking seed chunks and graph neighbors into the final context set.",
            {"seed_count": len(seeds), "neighbor_count": len(neighbours)},
            status="processing",
        )

        return self._rerank(seeds, neighbours)

    def _rerank(self, seeds: list[dict], neighbours: list[dict]) -> list[dict]:
        rrf_scores: dict[str, float] = {}
        chunks_by_id: dict[str, dict] = {}

        for rank, chunk in enumerate(seeds):
            chunk_id = chunk["id"]
            rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0.0) + 1.0 / (self._rrf_k + rank + 1)
            chunks_by_id[chunk_id] = chunk

        for rank, chunk in enumerate(neighbours):
            chunk_id = chunk["id"]
            rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0.0) + 1.0 / (self._rrf_k + rank + 1)
            chunks_by_id.setdefault(chunk_id, chunk)

        return [
            {
                "content": chunks_by_id[chunk_id]["text"],
                "score": score,
                "metadata": {
                    "source": chunks_by_id[chunk_id]["source"],
                    "chunk_index": chunks_by_id[chunk_id]["chunk_index"],
                },
            }
            for chunk_id, score in sorted(rrf_scores.items(), key=lambda item: item[1], reverse=True)
        ]


def graph_search(query: str) -> list[dict]:
    """
    1. Embed the query and find TOP_K seed Chunk nodes by vector similarity.
    2. Expand each seed up to GRAPH_MAX_HOPS via NEXT_CHUNK relationships.
    3. Re-rank with Reciprocal Rank Fusion (RRF_K smoothing).
    4. Return deduplicated chunks ordered by RRF score.
    """
    owner_id = current_user_id()
    if owner_id is None:
        return []
    return _cached_searcher().search(query, owner_id)


@lru_cache(maxsize=1)
def _cached_searcher() -> CachedGraphSearcher:
    return CachedGraphSearcher(
        searcher=Neo4jGraphSearcher(),
        cache=RedisRetrievalCache(),
        knowledge_bases=SqlKnowledgeBaseRepository(Database()),
        embeddings_factory=get_ollama_embeddings,
    )
