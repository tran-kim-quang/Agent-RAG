import base64
import json
import logging
from pathlib import Path
from typing import Callable
from uuid import uuid4

from langchain.tools import tool

from backend.process_raw_data.process_service import process_file
from backend.src.index.graph_index import build_graph_index
from backend.src.ingest.chunker import chunk_document
from backend.src.ingest.cleaner import clean_document

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_RAW_DATA_DIR = _PROJECT_ROOT / "data" / "raw"
_PROCESSED_DATA_DIR = _PROJECT_ROOT / "data" / "processed"
_SUPPORTED_SUFFIXES = {
    ".md",
    ".pdf",
    ".docx",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".bmp",
    ".gif",
}
ProgressCallback = Callable[[str, str, dict | None], None]


def _normalize_uploaded_filename(file_name: str) -> str:
    normalized = Path(file_name).name.strip()
    if not normalized:
        raise ValueError("Uploaded file name is empty.")
    return normalized


def _ensure_supported_suffix(file_name: str) -> None:
    suffix = Path(file_name).suffix.lower()
    if suffix not in _SUPPORTED_SUFFIXES:
        supported = ", ".join(sorted(_SUPPORTED_SUFFIXES))
        raise ValueError(f"Unsupported file type '{suffix}'. Supported: {supported}")


def _decode_uploaded_content(file_content_base64: str) -> bytes:
    try:
        return base64.b64decode(file_content_base64, validate=True)
    except Exception as exc:
        raise ValueError("Uploaded file content is not valid base64.") from exc


def _allocate_raw_path(file_name: str) -> Path:
    _RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)

    candidate = _RAW_DATA_DIR / file_name
    if not candidate.exists():
        return candidate

    stem = Path(file_name).stem
    suffix = Path(file_name).suffix
    return _RAW_DATA_DIR / f"{stem}_{uuid4().hex[:8]}{suffix}"


def _processed_output_paths(raw_path: Path) -> tuple[Path, Path]:
    markdown_path = (_PROCESSED_DATA_DIR / raw_path.stem).with_suffix(".md")
    metadata_path = markdown_path.with_suffix(".metadata.json")
    return markdown_path, metadata_path


def save_uploaded_file(file_name: str, file_bytes: bytes) -> Path:
    normalized_name = _normalize_uploaded_filename(file_name)
    _ensure_supported_suffix(normalized_name)

    logger.info(
        "[ingest/save_raw] Preparing raw file write: file_name=%s size_bytes=%s",
        normalized_name,
        len(file_bytes),
    )
    raw_path = _allocate_raw_path(normalized_name)
    raw_path.write_bytes(file_bytes)
    logger.info("[ingest/save_raw] Raw file saved: raw_path=%s", raw_path)
    return raw_path


def _emit_progress(
    callback: ProgressCallback | None,
    phase: str,
    message: str,
    details: dict | None = None,
) -> None:
    if callback is not None:
        callback(phase, message, details)


def process_and_ingest_uploaded_file(
    file_name: str,
    file_bytes: bytes,
    progress_callback: ProgressCallback | None = None,
) -> dict:
    """Save an uploaded file into data/raw, process it, write markdown, and ingest to Neo4j."""
    logger.info("[ingest/start] Starting ingest pipeline: file_name=%s", file_name)
    _emit_progress(progress_callback, "start", f"Starting ingest for {file_name}")
    raw_path = save_uploaded_file(file_name, file_bytes)
    _emit_progress(
        progress_callback,
        "save_raw",
        f"Saved raw file {raw_path.name}",
        {"raw_path": str(raw_path)},
    )

    _emit_progress(progress_callback, "process", f"Processing raw file {raw_path.name}")
    logger.info("[ingest/process] Processing raw file: raw_path=%s", raw_path)
    extracted = process_file(raw_path)
    if extracted is None:
        logger.error("[ingest/process] Unsupported or empty processing result: raw_path=%s", raw_path)
        raise ValueError(f"Could not process uploaded file: {raw_path.name}")
    logger.info(
        "[ingest/process] Processing complete: raw_path=%s content_chars=%s",
        raw_path,
        len(extracted["content"]),
    )

    markdown_path, metadata_path = _processed_output_paths(raw_path)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)

    processed_doc = {
        "content": extracted["content"],
        "metadata": {
            **extracted["metadata"],
            "source": str(markdown_path),
            "raw_source": str(raw_path),
            "processed_metadata_path": str(metadata_path),
            "original_file_name": file_name,
        },
    }

    markdown_path.write_text(processed_doc["content"], encoding="utf-8")
    metadata_path.write_text(
        json.dumps(processed_doc["metadata"], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _emit_progress(
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
    _emit_progress(progress_callback, "clean", f"Cleaning processed text for {raw_path.name}")
    cleaned_doc = clean_document(processed_doc)
    logger.info("[ingest/chunk] Chunking cleaned document: source=%s", cleaned_doc["metadata"].get("source"))
    _emit_progress(
        progress_callback,
        "chunk",
        f"Chunking document {markdown_path.name}",
        {"processed_path": str(markdown_path)},
    )
    chunks = chunk_document(cleaned_doc)
    logger.info("[ingest/chunk] Chunking complete: chunk_count=%s", len(chunks))
    _emit_progress(
        progress_callback,
        "chunk_complete",
        f"Chunking complete: {len(chunks)} chunks",
        {"chunk_count": len(chunks), "processed_path": str(markdown_path)},
    )

    logger.info("[ingest/index] Building Neo4j graph index: chunk_count=%s", len(chunks))
    _emit_progress(
        progress_callback,
        "index_start",
        f"Indexing {len(chunks)} chunks into Neo4j",
        {"chunk_count": len(chunks), "processed_path": str(markdown_path)},
    )
    build_graph_index(chunks, progress_callback=progress_callback)
    logger.info("[ingest/index] Neo4j graph index complete: source=%s", markdown_path)

    result = {
        "raw_path": str(raw_path),
        "processed_path": str(markdown_path),
        "metadata_path": str(metadata_path),
        "chunk_count": len(chunks),
        "source_name": processed_doc["metadata"].get("name", raw_path.stem),
    }
    _emit_progress(
        progress_callback,
        "done",
        f"Completed ingest for {raw_path.name}",
        {
            "raw_path": str(raw_path),
            "processed_path": str(markdown_path),
            "metadata_path": str(metadata_path),
            "chunk_count": len(chunks),
            "source_name": processed_doc["metadata"].get("name", raw_path.stem),
        },
    )
    logger.info("[ingest/done] Ingest pipeline finished: result=%s", result)
    return result


@tool
def process_data_tool(file_name: str, file_content_base64: str) -> str:
    """
    Process one file uploaded from the frontend.
    Save the uploaded file into data/raw, write processed markdown into data/processed,
    and ingest the processed content into Neo4j.
    """
    logger.info("[ingest/decode] Decoding uploaded file content: file_name=%s", file_name)
    file_bytes = _decode_uploaded_content(file_content_base64)
    result = process_and_ingest_uploaded_file(file_name, file_bytes)
    return (
        f"Processed '{result['source_name']}' successfully.\n"
        f"- raw_path: {result['raw_path']}\n"
        f"- processed_path: {result['processed_path']}\n"
        f"- metadata_path: {result['metadata_path']}\n"
        f"- chunks_ingested: {result['chunk_count']}"
    )
