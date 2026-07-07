import os
from dotenv import load_dotenv
from langchain_community.embeddings import OllamaEmbeddings
from langchain_experimental.text_splitter import SemanticChunker

from backend.src.core.models import ChunkRecord, DocumentRecord

load_dotenv()

_embeddings = None


def _get_embeddings():
    global _embeddings
    if _embeddings is None:
        base_url = os.getenv("OLLAMA_LOCAL_URL", "http://localhost:11434/v1").replace("/v1", "")
        _embeddings = OllamaEmbeddings(
            model=os.getenv("EMBEDDING_MODEL_NAME"),
            base_url=base_url,
        )
    return _embeddings


class SemanticDocumentChunker:
    def __init__(self, embeddings_factory=_get_embeddings) -> None:
        self._embeddings_factory = embeddings_factory

    def chunk(self, document: DocumentRecord) -> list[ChunkRecord]:
        splitter = SemanticChunker(
            embeddings=self._embeddings_factory(),
            breakpoint_threshold_type="percentile",
        )
        chunks = splitter.create_documents([document.content])
        return [
            ChunkRecord(
                content=chunk.page_content,
                metadata={**document.metadata, "chunk_index": i},
            )
            for i, chunk in enumerate(chunks)
        ]


def chunk_document(doc: dict) -> list[dict]:
    chunker = SemanticDocumentChunker()
    document = DocumentRecord.from_dict(doc)
    return [chunk.to_dict() for chunk in chunker.chunk(document)]


def chunk_documents(documents: list[dict]) -> list[dict]:
    result = []
    for doc in documents:
        result.extend(chunk_document(doc))
    return result
