import logging
import os

from langchain_core.documents import Document
from langchain_experimental.text_splitter import SemanticChunker
from langchain_text_splitters import RecursiveCharacterTextSplitter

from backend.src.core.models import ChunkRecord, DocumentRecord
from backend.src.core.ports import ProgressCallback
from backend.src.infrastructure import get_ollama_embeddings, load_config

logger = logging.getLogger(__name__)


class SemanticDocumentChunker:
    def __init__(self, embeddings_factory=get_ollama_embeddings, config_loader=load_config) -> None:
        self._embeddings_factory = embeddings_factory
        self._config_loader = config_loader

    def chunk(
        self,
        document: DocumentRecord,
        progress_callback: ProgressCallback | None = None,
    ) -> list[ChunkRecord]:
        config = self._config_loader()
        chunking_config = config.get("chunking", {})
        window_size = int(
            os.getenv(
                "SEMANTIC_WINDOW_SIZE",
                str(chunking_config.get("semantic_window_size", 3000)),
            )
        )
        window_overlap = min(
            int(
                os.getenv(
                    "SEMANTIC_WINDOW_OVERLAP",
                    str(chunking_config.get("semantic_window_overlap", 200)),
                )
            ),
            max(0, window_size - 1),
        )
        input_splitter = RecursiveCharacterTextSplitter(
            chunk_size=window_size,
            chunk_overlap=window_overlap,
        )
        semantic_inputs = input_splitter.create_documents(
            [document.content],
            metadatas=[document.metadata],
        )
        semantic_splitter = SemanticChunker(
            embeddings=self._embeddings_factory(),
            breakpoint_threshold_type="percentile",
        )
        semantic_chunks: list[Document] = []
        total_windows = len(semantic_inputs)
        for index, semantic_input in enumerate(semantic_inputs, start=1):
            try:
                semantic_chunks.extend(
                    semantic_splitter.create_documents(
                        [semantic_input.page_content],
                        metadatas=[semantic_input.metadata],
                    )
                )
            except ValueError as exc:
                if "context length" not in str(exc).lower():
                    raise
                logger.warning(
                    "Semantic embedding exceeded model context; using bounded window: window=%s/%s",
                    index,
                    total_windows,
                )
                semantic_chunks.append(semantic_input)
            if progress_callback is not None:
                progress_callback(
                    "chunk",
                    f"Semantic chunking window {index} of {total_windows}.",
                    {
                        "progress": 55 + int((index / total_windows) * 9),
                        "processed_windows": index,
                        "total_windows": total_windows,
                    },
                )
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
