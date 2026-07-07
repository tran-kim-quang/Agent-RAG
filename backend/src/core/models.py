from __future__ import annotations

from dataclasses import dataclass
from typing import Any


Metadata = dict[str, Any]


@dataclass(slots=True)
class DocumentRecord:
    content: str
    metadata: Metadata

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "DocumentRecord":
        return cls(
            content=payload["content"],
            metadata=dict(payload["metadata"]),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "content": self.content,
            "metadata": dict(self.metadata),
        }


@dataclass(slots=True)
class ChunkRecord:
    content: str
    metadata: Metadata

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ChunkRecord":
        return cls(
            content=payload["content"],
            metadata=dict(payload["metadata"]),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "content": self.content,
            "metadata": dict(self.metadata),
        }


@dataclass(slots=True)
class IngestResult:
    raw_path: str
    processed_path: str
    metadata_path: str
    chunk_count: int
    source_name: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "raw_path": self.raw_path,
            "processed_path": self.processed_path,
            "metadata_path": self.metadata_path,
            "chunk_count": self.chunk_count,
            "source_name": self.source_name,
        }
