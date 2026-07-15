from langchain_core.documents import Document
from langchain_experimental.text_splitter import SemanticChunker
from langchain_text_splitters import RecursiveCharacterTextSplitter

from backend.src.core.models import ChunkRecord, DocumentRecord
from backend.src.infrastructure import get_ollama_embeddings, load_config


class SemanticDocumentChunker:
    def __init__(self, embeddings_factory=get_ollama_embeddings, config_loader=load_config) -> None:
        self._embeddings_factory = embeddings_factory
        self._config_loader = config_loader

    def chunk(self, document: DocumentRecord) -> list[ChunkRecord]:
        semantic_splitter = SemanticChunker(
            embeddings=self._embeddings_factory(),
            breakpoint_threshold_type="percentile",
        )
        semantic_chunks = semantic_splitter.create_documents(
            [document.content],
            metadatas=[document.metadata],
        )
        config = self._config_loader()
        chunking_config = config.get("chunking", {})
        size_splitter = RecursiveCharacterTextSplitter(
            chunk_size=int(chunking_config.get("chunk_size", 1000)),
            chunk_overlap=int(chunking_config.get("chunk_overlap", 200)),
        )
        bounded_chunks: list[Document] = size_splitter.split_documents(semantic_chunks)

        return [
            ChunkRecord(
                content=chunk.page_content,
                metadata={**chunk.metadata, **document.metadata, "chunk_index": i},
            )
            for i, chunk in enumerate(bounded_chunks)
            if chunk.page_content.strip()
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
