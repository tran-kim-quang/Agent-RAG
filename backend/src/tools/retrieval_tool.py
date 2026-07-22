from langchain.tools import tool

from backend.src.monitoring import agent_run_monitor
from backend.src.retrieval.cached_search import RetrievalOutcome
from backend.src.retrieval.graph_search import graph_search_with_artifact


@tool(response_format="content_and_artifact")
def graph_search_tool(query: str) -> tuple[str, dict]:
    """
    Search the document graph index.
    Finds the most relevant document chunks by semantic similarity,
    then expands context via document relationships (NEXT_CHUNK).
    Input should be a search query string.
    """
    agent_run_monitor.append_event(
        "graph_search_tool_start",
        "Retrieval tool is querying the indexed document graph.",
        {"query_length": len(query)},
        status="processing",
    )
    outcome = graph_search_with_artifact(query)
    results = [] if outcome is None else outcome.results

    if not results:
        agent_run_monitor.append_event(
            "graph_search_tool_complete",
            "Retrieval tool found no relevant chunks.",
            {"result_count": 0},
            status="processing",
        )
        return "No relevant documents found.", _empty_artifact(query, outcome)

    parts = []
    for i, r in enumerate(results, 1):
        score = r.get("rerank_score", r.get("score"))
        score_str = f"(rerank score: {score:.4f})" if score is not None else "(related)"
        source = r["metadata"].get("source", "unknown")
        chunk_index = r["metadata"].get("chunk_index", "?")
        parts.append(
            f"[{i}] {score_str} source={source}, chunk={chunk_index}\n{r['content']}"
        )

    agent_run_monitor.append_event(
        "graph_search_tool_complete",
        "Retrieval tool found relevant chunks from the document graph.",
        {"result_count": len(results)},
        status="processing",
    )
    artifact = _build_artifact(outcome)
    quality = artifact["quality"]
    summary = (
        f"Retrieval metadata: cache={artifact['cache_status']}, "
        f"results={quality['result_count']}, sources={quality['source_count']}, "
        f"top_rerank_score={quality['top_rerank_score']}."
    )
    return f"{summary}\n\n" + "\n\n---\n\n".join(parts), artifact


def _build_artifact(outcome: RetrievalOutcome) -> dict:
    chunks = []
    citations = []
    scores = []
    sources = set()
    for index, result in enumerate(outcome.results, start=1):
        metadata = result.get("metadata", {})
        source = str(metadata.get("source", "unknown"))
        rerank_score = result.get("rerank_score", result.get("score"))
        retrieval_score = result.get("retrieval_score")
        citation_id = f"doc-{index}"
        sources.add(source)
        if rerank_score is not None:
            scores.append(float(rerank_score))
        chunks.append(
            {
                "citation_id": citation_id,
                "content": result.get("content", ""),
                "source": source,
                "chunk_index": metadata.get("chunk_index"),
                "retrieval_score": retrieval_score,
                "rerank_score": rerank_score,
            }
        )
        citations.append(
            {
                "citation_id": citation_id,
                "source": source,
                "chunk_index": metadata.get("chunk_index"),
                "rerank_score": rerank_score,
            }
        )
    return {
        "kind": "retrieval_evidence",
        "query": outcome.query,
        "normalized_query": outcome.normalized_query,
        "knowledge_base_version": outcome.knowledge_base_version,
        "cache_status": outcome.cache_status,
        "reranker_model": outcome.reranker_model,
        "quality": {
            "result_count": len(chunks),
            "source_count": len(sources),
            "top_rerank_score": max(scores) if scores else None,
            "mean_rerank_score": sum(scores) / len(scores) if scores else None,
        },
        "citations": citations,
        "chunks": chunks,
    }


def _empty_artifact(query: str, outcome: RetrievalOutcome | None) -> dict:
    return {
        "kind": "retrieval_evidence",
        "query": query,
        "normalized_query": outcome.normalized_query if outcome else query,
        "knowledge_base_version": outcome.knowledge_base_version if outcome else None,
        "cache_status": outcome.cache_status if outcome else "unavailable",
        "reranker_model": outcome.reranker_model if outcome else None,
        "quality": {"result_count": 0, "source_count": 0, "top_rerank_score": None, "mean_rerank_score": None},
        "citations": [],
        "chunks": [],
    }
