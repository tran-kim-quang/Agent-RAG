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
