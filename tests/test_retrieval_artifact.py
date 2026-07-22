from backend.src.retrieval.cached_search import RetrievalOutcome
from backend.src.tools.retrieval_tool import _build_artifact


def test_retrieval_artifact_exposes_scores_citations_and_cache_metadata() -> None:
    outcome = RetrievalOutcome(
        query="question",
        normalized_query="question",
        owner_id="user-1",
        knowledge_base_version=4,
        cache_status="semantic_hit",
        reranker_model="BAAI/bge-reranker-v2-m3",
        results=[
            {
                "content": "answer",
                "score": 0.91,
                "retrieval_score": 0.03,
                "rerank_score": 0.91,
                "metadata": {"source": "document.md", "chunk_index": 2},
            }
        ],
    )

    artifact = _build_artifact(outcome)

    assert artifact["cache_status"] == "semantic_hit"
    assert artifact["knowledge_base_version"] == 4
    assert artifact["quality"] == {
        "result_count": 1,
        "source_count": 1,
        "top_rerank_score": 0.91,
        "mean_rerank_score": 0.91,
    }
    assert artifact["citations"][0]["citation_id"] == "doc-1"
    assert artifact["chunks"][0]["retrieval_score"] == 0.03
