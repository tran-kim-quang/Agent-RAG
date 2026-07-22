from langchain_core.documents import Document

from backend.src.ingest import chunker


def test_semantic_chunker_applies_recursive_bounds_from_config(monkeypatch):
    class FakeSemanticChunker:
        def __init__(self, embeddings, breakpoint_threshold_type):
            self.embeddings = embeddings
            self.breakpoint_threshold_type = breakpoint_threshold_type

        def create_documents(self, texts, metadatas=None):
            return [Document(page_content=texts[0], metadata=(metadatas or [{}])[0])]

    monkeypatch.setattr(chunker, "SemanticChunker", FakeSemanticChunker)

    document = {
        "content": " ".join(["alpha"] * 120),
        "metadata": {"source": "unit-test.md", "source_type": "md"},
    }
    test_chunker = chunker.SemanticDocumentChunker(
        embeddings_factory=lambda: object(),
        config_loader=lambda: {"chunking": {"chunk_size": 80, "chunk_overlap": 10}},
    )

    chunks = test_chunker.chunk(chunker.DocumentRecord.from_dict(document))

    assert len(chunks) > 1
    assert all(len(item.content) <= 80 for item in chunks)
    assert [item.metadata["chunk_index"] for item in chunks] == list(range(len(chunks)))
    assert all(item.metadata["source"] == "unit-test.md" for item in chunks)


def test_semantic_chunker_bounds_embedding_inputs_and_reports_progress(monkeypatch):
    embedded_lengths: list[int] = []

    class FakeSemanticChunker:
        def __init__(self, embeddings, breakpoint_threshold_type):
            pass

        def create_documents(self, texts, metadatas=None):
            embedded_lengths.append(len(texts[0]))
            return [Document(page_content=texts[0], metadata=(metadatas or [{}])[0])]

    monkeypatch.setattr(chunker, "SemanticChunker", FakeSemanticChunker)
    progress: list[dict] = []
    test_chunker = chunker.SemanticDocumentChunker(
        embeddings_factory=lambda: object(),
        config_loader=lambda: {
            "chunking": {
                "semantic_window_size": 120,
                "semantic_window_overlap": 10,
                "chunk_size": 80,
                "chunk_overlap": 10,
            }
        },
    )

    chunks = test_chunker.chunk(
        chunker.DocumentRecord(
            content=" ".join(["semantic"] * 100),
            metadata={"source": "large.md"},
        ),
        lambda phase, message, details: progress.append({"phase": phase, **(details or {})}),
    )

    assert chunks
    assert len(embedded_lengths) > 1
    assert max(embedded_lengths) <= 120
    assert progress[-1]["processed_windows"] == progress[-1]["total_windows"]
