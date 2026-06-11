import os
import yaml
from pathlib import Path
from dotenv import load_dotenv
from neo4j import GraphDatabase
from langchain_community.embeddings import OllamaEmbeddings

load_dotenv()

_CONFIG_PATH = Path(__file__).parents[2] / "configs" / "config.yaml"

with open(_CONFIG_PATH) as _f:
    _CFG = yaml.safe_load(_f)["retriever"]

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


def graph_search(query: str) -> list[dict]:
    """
    1. Embed the query and find TOP_K seed Chunk nodes by vector similarity.
    2. Expand each seed up to GRAPH_MAX_HOPS via NEXT_CHUNK relationships.
    3. Re-rank with Reciprocal Rank Fusion (RRF_K smoothing).
    4. Return deduplicated chunks ordered by RRF score.
    """
    top_k = TOP_K
    max_hops = GRAPH_MAX_HOPS
    rrf_k = RRF_K

    query_embedding = _get_embeddings().embed_query(query)

    driver = _neo4j_driver()
    with driver.session() as session:
        # Step 1: vector similarity search for seed nodes
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
            top_k=top_k,
            embedding=query_embedding,
        )
        seeds = [dict(r) for r in seed_result]

        if not seeds:
            return []

        seed_ids = [s["id"] for s in seeds]

        # Step 2: expand via NEXT_CHUNK relationships up to max_hops
        # max_hops must be a literal in the path pattern — parameters are not allowed there
        neighbour_result = session.run(
            f"""
            UNWIND $seed_ids AS seedId
            MATCH (seed)
            WHERE elementId(seed) = seedId
            MATCH path = (seed)-[:NEXT_CHUNK*1..{max_hops}]-(neighbour:Chunk)
            RETURN DISTINCT
                elementId(neighbour) AS id,
                neighbour.text        AS text,
                neighbour.source      AS source,
                neighbour.chunk_index AS chunk_index
            """,
            seed_ids=seed_ids,
        )
        neighbours = [dict(r) for r in neighbour_result]

    driver.close()

    # RRF: score = 1 / (rrf_k + rank) summed across lists
    rrf_scores: dict[str, float] = {}
    chunks_by_id: dict[str, dict] = {}

    for rank, chunk in enumerate(seeds):
        cid = chunk["id"]
        rrf_scores[cid] = rrf_scores.get(cid, 0.0) + 1.0 / (rrf_k + rank + 1)
        chunks_by_id[cid] = chunk

    for rank, chunk in enumerate(neighbours):
        cid = chunk["id"]
        rrf_scores[cid] = rrf_scores.get(cid, 0.0) + 1.0 / (rrf_k + rank + 1)
        chunks_by_id.setdefault(cid, chunk)

    results = [
        {
            "content": chunks_by_id[cid]["text"],
            "score": score,
            "metadata": {
                "source": chunks_by_id[cid]["source"],
                "chunk_index": chunks_by_id[cid]["chunk_index"],
            },
        }
        for cid, score in sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
    ]

    return results
