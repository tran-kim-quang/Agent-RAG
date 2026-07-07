import os
from pathlib import Path
from typing import Callable

import yaml
from dotenv import load_dotenv
from langchain_community.embeddings import OllamaEmbeddings
from neo4j import GraphDatabase

from backend.src.monitoring import agent_run_monitor

load_dotenv()

_CONFIG_PATH = Path(__file__).parents[2] / "configs" / "config.yaml"

with open(_CONFIG_PATH, encoding="utf-8") as handle:
    _CFG = yaml.safe_load(handle)["retriever"]

TOP_K: int = _CFG["top_k"]
GRAPH_MAX_HOPS: int = _CFG["graph_max_hops"]
RRF_K: int = _CFG["rrf_k"]


def _get_embeddings() -> OllamaEmbeddings:
    base_url = os.getenv("OLLAMA_LOCAL_URL", "http://localhost:11434/v1").replace("/v1", "")
    return OllamaEmbeddings(
        model=os.getenv("EMBEDDING_MODEL_NAME"),
        base_url=base_url,
    )


def _neo4j_driver():
    return GraphDatabase.driver(
        os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        auth=(
            os.getenv("NEO4J_USERNAME", "neo4j"),
            os.getenv("NEO4J_PASSWORD", "password"),
        ),
    )


class Neo4jGraphSearcher:
    def __init__(
        self,
        embeddings_factory: Callable[[], OllamaEmbeddings] = _get_embeddings,
        driver_factory: Callable[[], object] = _neo4j_driver,
        top_k: int = TOP_K,
        max_hops: int = GRAPH_MAX_HOPS,
        rrf_k: int = RRF_K,
    ) -> None:
        self._embeddings_factory = embeddings_factory
        self._driver_factory = driver_factory
        self._top_k = top_k
        self._max_hops = max_hops
        self._rrf_k = rrf_k

    def search(self, query: str) -> list[dict]:
        agent_run_monitor.append_event(
            "embed_query",
            "Generating the query embedding for semantic retrieval.",
            status="processing",
        )
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
                CALL db.index.vector.queryNodes('document_chunks', $top_k, $embedding)
                YIELD node AS chunk, score
                RETURN
                    elementId(chunk)   AS id,
                    chunk.text         AS text,
                    chunk.source       AS source,
                    chunk.chunk_index  AS chunk_index,
                    score
                ORDER BY score DESC
                """,
                top_k=self._top_k,
                embedding=query_embedding,
            )
            seeds = [dict(record) for record in seed_result]

            if not seeds:
                agent_run_monitor.append_event(
                    "vector_search_complete",
                    "Vector search returned no seed chunks.",
                    {"seed_count": 0},
                    status="processing",
                )
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
                RETURN DISTINCT
                    elementId(neighbour) AS id,
                    neighbour.text        AS text,
                    neighbour.source      AS source,
                    neighbour.chunk_index AS chunk_index
                """,
                seed_ids=seed_ids,
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
    return Neo4jGraphSearcher().search(query)
