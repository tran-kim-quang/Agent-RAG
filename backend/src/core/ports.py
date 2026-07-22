from __future__ import annotations

from pathlib import Path
from typing import Callable, Protocol, TypeAlias

from backend.src.core.models import ChunkRecord, DocumentRecord


ProgressDetails: TypeAlias = dict | None
ProgressCallback: TypeAlias = Callable[[str, str, ProgressDetails], None]


class DocumentProcessor(Protocol):
    def process(
        self,
        file_path: str | Path,
        progress_callback: ProgressCallback | None = None,
    ) -> DocumentRecord | None:
        ...


class DocumentCleaner(Protocol):
    def clean(self, document: DocumentRecord) -> DocumentRecord:
        ...


class DocumentChunker(Protocol):
    def chunk(
        self,
        document: DocumentRecord,
        progress_callback: ProgressCallback | None = None,
    ) -> list[ChunkRecord]:
        ...


class UploadedFileStorage(Protocol):
    def save(self, file_name: str, file_bytes: bytes) -> Path:
        ...


class GraphIndexer(Protocol):
    def build_index(
        self,
        chunks: list[ChunkRecord],
        progress_callback: ProgressCallback | None = None,
    ) -> None:
        ...


class GraphSearcher(Protocol):
    def search(self, query: str, owner_id: str | None = None) -> list[dict]:
        ...


class EmbeddingClient(Protocol):
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        ...

    def embed_query(self, text: str) -> list[float]:
        ...
