from backend.src.retrieval.cached_search import CachedGraphSearcher, normalize_query


class FakeEmbeddings:
    def __init__(self) -> None:
        self.calls = 0

    def embed_query(self, _: str) -> list[float]:
        self.calls += 1
        return [1.0, 0.0]


class FakeVersions:
    def get_version(self, _: str) -> int:
        return 3


class FakeSearcher:
    def __init__(self) -> None:
        self.calls = 0

    def search(self, query: str, owner_id: str | None = None, query_embedding: list[float] | None = None) -> list[dict]:
        self.calls += 1
        return [{"content": query, "score": 1.0, "metadata": {"source": owner_id}}]


class FakeCache:
    def __init__(self, exact=None, semantic=None) -> None:
        self.exact = exact
        self.semantic = semantic
        self.saved = None

    def get_exact(self, *_): return self.exact
    def get_semantic(self, *_): return self.semantic
    def put(self, *args): self.saved = args


def test_normalize_query_is_stable() -> None:
    assert normalize_query("  Xin   CHAO\nBan ") == "xin chao ban"


def test_exact_cache_skips_embedding_and_graph_search() -> None:
    cached = [{"content": "cached"}]
    embeddings, searcher = FakeEmbeddings(), FakeSearcher()
    service = CachedGraphSearcher(searcher, FakeCache(exact=cached), FakeVersions(), lambda: embeddings)

    assert service.search("question", "owner") == cached
    assert embeddings.calls == 0
    assert searcher.calls == 0


def test_semantic_cache_skips_graph_search() -> None:
    cached = [{"content": "similar"}]
    embeddings, searcher = FakeEmbeddings(), FakeSearcher()
    service = CachedGraphSearcher(searcher, FakeCache(semantic=cached), FakeVersions(), lambda: embeddings)

    assert service.search("question", "owner") == cached
    assert embeddings.calls == 1
    assert searcher.calls == 0


def test_cache_miss_queries_graph_and_saves_results() -> None:
    embeddings, searcher, cache = FakeEmbeddings(), FakeSearcher(), FakeCache()
    service = CachedGraphSearcher(searcher, cache, FakeVersions(), lambda: embeddings)

    result = service.search("Question", "owner")

    assert searcher.calls == 1
    assert cache.saved == ("owner", 3, "question", [1.0, 0.0], result)
