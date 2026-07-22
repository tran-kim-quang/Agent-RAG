from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Callable
from uuid import uuid4

from backend.src.core.models import DocumentRecord, IngestResult
from backend.src.core.ports import (
    DocumentChunker,
    DocumentCleaner,
    DocumentProcessor,
    GraphIndexer,
    UploadedFileStorage,
)

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str, str, dict | None], None]


class LocalUploadedFileStorage:
    def __init__(self, raw_data_dir: Path, supported_suffixes: set[str]) -> None:
        self._raw_data_dir = raw_data_dir
        self._supported_suffixes = {suffix.lower() for suffix in supported_suffixes}

    def save(self, file_name: str, file_bytes: bytes) -> Path:
        normalized_name = self._normalize_uploaded_filename(file_name)
        self._ensure_supported_suffix(normalized_name)

        logger.info(
            "[ingest/save_raw] Preparing raw file write: file_name=%s size_bytes=%s",
            normalized_name,
            len(file_bytes),
        )
        raw_path = self._allocate_raw_path(normalized_name)
        raw_path.write_bytes(file_bytes)
        logger.info("[ingest/save_raw] Raw file saved: raw_path=%s", raw_path)
        return raw_path

    def _normalize_uploaded_filename(self, file_name: str) -> str:
        normalized = Path(file_name).name.strip()
        if not normalized:
            raise ValueError("Uploaded file name is empty.")
        return normalized

    def _ensure_supported_suffix(self, file_name: str) -> None:
        suffix = Path(file_name).suffix.lower()
        if suffix not in self._supported_suffixes:
            supported = ", ".join(sorted(self._supported_suffixes))
            raise ValueError(f"Unsupported file type '{suffix}'. Supported: {supported}")

    def _allocate_raw_path(self, file_name: str) -> Path:
        self._raw_data_dir.mkdir(parents=True, exist_ok=True)

        candidate = self._raw_data_dir / file_name
        if not candidate.exists():
            return candidate

        stem = Path(file_name).stem
        suffix = Path(file_name).suffix
        return self._raw_data_dir / f"{stem}_{uuid4().hex[:8]}{suffix}"


class UploadedFileIngestService:
    def __init__(
        self,
        storage: UploadedFileStorage,
        processor: DocumentProcessor,
        cleaner: DocumentCleaner,
        chunker: DocumentChunker,
        graph_indexer: GraphIndexer,
        processed_data_dir: Path,
    ) -> None:
        self._storage = storage
        self._processor = processor
        self._cleaner = cleaner
        self._chunker = chunker
        self._graph_indexer = graph_indexer
        self._processed_data_dir = processed_data_dir

    def ingest_uploaded_file(
        self,
        file_name: str,
        file_bytes: bytes,
        progress_callback: ProgressCallback | None = None,
    ) -> IngestResult:
        logger.info("[ingest/start] Starting ingest pipeline: file_name=%s", file_name)
        self._emit_progress(progress_callback, "start", f"Starting ingest for {file_name}")

        raw_path = self._storage.save(file_name, file_bytes)
        self._emit_progress(
            progress_callback,
            "save_raw",
            f"Saved raw file {raw_path.name}",
            {"raw_path": str(raw_path)},
        )

        self._emit_progress(progress_callback, "process", f"Processing raw file {raw_path.name}")
        logger.info("[ingest/process] Processing raw file: raw_path=%s", raw_path)
        extracted = self._processor.process(raw_path, progress_callback)
        if extracted is None:
            logger.error("[ingest/process] Unsupported or empty processing result: raw_path=%s", raw_path)
            raise ValueError(f"Could not process uploaded file: {raw_path.name}")
        logger.info(
            "[ingest/process] Processing complete: raw_path=%s content_chars=%s",
            raw_path,
            len(extracted.content),
        )

        markdown_path, metadata_path = self._processed_output_paths(raw_path)
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        processed_doc = DocumentRecord(
            content=extracted.content,
            metadata={
                **extracted.metadata,
                "source": str(markdown_path),
                "raw_source": str(raw_path),
                "processed_metadata_path": str(metadata_path),
                "original_file_name": file_name,
            },
        )

        markdown_path.write_text(processed_doc.content, encoding="utf-8")
        metadata_path.write_text(
            json.dumps(processed_doc.metadata, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self._emit_progress(
            progress_callback,
            "write_processed",
            f"Wrote processed files for {raw_path.name}",
            {
                "raw_path": str(raw_path),
                "processed_path": str(markdown_path),
                "metadata_path": str(metadata_path),
            },
        )
        logger.info(
            "[ingest/write_processed] Processed files written: processed_path=%s metadata_path=%s",
            markdown_path,
            metadata_path,
        )

        logger.info("[ingest/clean] Cleaning processed document: processed_path=%s", markdown_path)
        self._emit_progress(progress_callback, "clean", f"Cleaning processed text for {raw_path.name}")
        cleaned_doc = self._cleaner.clean(processed_doc)

        logger.info("[ingest/chunk] Chunking cleaned document: source=%s", cleaned_doc.metadata.get("source"))
        self._emit_progress(
            progress_callback,
            "chunk",
            f"Chunking document {markdown_path.name}",
            {"processed_path": str(markdown_path)},
        )
        chunks = self._chunker.chunk(cleaned_doc, progress_callback)
        logger.info("[ingest/chunk] Chunking complete: chunk_count=%s", len(chunks))
        self._emit_progress(
            progress_callback,
            "chunk_complete",
            f"Chunking complete: {len(chunks)} chunks",
            {"chunk_count": len(chunks), "processed_path": str(markdown_path)},
        )

        logger.info("[ingest/index] Building Neo4j graph index: chunk_count=%s", len(chunks))
        self._emit_progress(
            progress_callback,
            "index_start",
            f"Indexing {len(chunks)} chunks into Neo4j",
            {"chunk_count": len(chunks), "processed_path": str(markdown_path)},
        )
        self._graph_indexer.build_index(chunks, progress_callback=progress_callback)
        logger.info("[ingest/index] Neo4j graph index complete: source=%s", markdown_path)

        result = IngestResult(
            raw_path=str(raw_path),
            processed_path=str(markdown_path),
            metadata_path=str(metadata_path),
            chunk_count=len(chunks),
            source_name=processed_doc.metadata.get("name", raw_path.stem),
        )
        self._emit_progress(
            progress_callback,
            "done",
            f"Completed ingest for {raw_path.name}",
            result.to_dict(),
        )
        logger.info("[ingest/done] Ingest pipeline finished: result=%s", result.to_dict())
        return result

    def _processed_output_paths(self, raw_path: Path) -> tuple[Path, Path]:
        markdown_path = (self._processed_data_dir / raw_path.stem).with_suffix(".md")
        metadata_path = markdown_path.with_suffix(".metadata.json")
        return markdown_path, metadata_path

    @staticmethod
    def _emit_progress(
        callback: ProgressCallback | None,
        phase: str,
        message: str,
        details: dict | None = None,
    ) -> None:
        if callback is not None:
            callback(phase, message, details)
