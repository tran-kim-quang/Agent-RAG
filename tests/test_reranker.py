from backend.src.retrieval.reranker import BgeCrossEncoderReranker


class FakeBgeReranker(BgeCrossEncoderReranker):
    def __init__(self) -> None:
        super().__init__(top_n=2)

    def _score(self, query: str, passages: list[str]) -> list[float]:
        assert query == "question"
        return [{"weak": 0.1, "best": 0.9, "good": 0.7}[passage] for passage in passages]


class WarmableBgeReranker(BgeCrossEncoderReranker):
    def __init__(self) -> None:
        super().__init__()
        self.loaded = False

    def _load_bundle(self) -> dict:
        self.loaded = True
        return {}


def test_bge_reranker_orders_candidates_and_preserves_retrieval_score() -> None:
    candidates = [
        {"content": "weak", "score": 0.8, "metadata": {"source": "a"}},
        {"content": "best", "score": 0.5, "metadata": {"source": "b"}},
        {"content": "good", "score": 0.6, "metadata": {"source": "c"}},
    ]

    ranked = FakeBgeReranker().rerank("question", candidates)

    assert [item["content"] for item in ranked] == ["best", "good"]
    assert ranked[0]["rerank_score"] == 0.9
    assert ranked[0]["retrieval_score"] == 0.5
    assert ranked[0]["score"] == 0.9


def test_reranker_can_be_warmed_without_running_inference() -> None:
    reranker = WarmableBgeReranker()

    reranker.warmup()

    assert reranker.loaded is True
