import base64
import logging
from pathlib import Path
from typing import Callable

from langchain.tools import tool

from backend.process_raw_data.process_service import DocumentProcessingService
from backend.src.index.graph_index import Neo4jGraphIndexer
from backend.src.ingest.chunker import SemanticDocumentChunker
from backend.src.ingest.cleaner import DefaultDocumentCleaner
from backend.src.ingest.service import LocalUploadedFileStorage, UploadedFileIngestService

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


def _decode_uploaded_content(file_content_base64: str) -> bytes:
    try:
        return base64.b64decode(file_content_base64, validate=True)
    except Exception as exc:
        raise ValueError("Uploaded file content is not valid base64.") from exc


def _build_ingest_service() -> UploadedFileIngestService:
    return UploadedFileIngestService(
        storage=LocalUploadedFileStorage(
            raw_data_dir=_RAW_DATA_DIR,
            supported_suffixes=_SUPPORTED_SUFFIXES,
        ),
        processor=DocumentProcessingService(),
        cleaner=DefaultDocumentCleaner(),
        chunker=SemanticDocumentChunker(),
        graph_indexer=Neo4jGraphIndexer(),
        processed_data_dir=_PROCESSED_DATA_DIR,
    )


def process_and_ingest_uploaded_file(
    file_name: str,
    file_bytes: bytes,
    progress_callback: ProgressCallback | None = None,
) -> dict:
    result = _build_ingest_service().ingest_uploaded_file(
        file_name=file_name,
        file_bytes=file_bytes,
        progress_callback=progress_callback,
    )
    return result.to_dict()


@tool
def process_data_tool(file_name: str, file_content_base64: str) -> str:
    """
    Process one file uploaded from the frontend.
    Save the uploaded file into data/raw, write processed markdown into data/processed,
    and ingest the processed content into Neo4j.
    """
    logger.info("[ingest/decode] Decoding uploaded file content: file_name=%s", file_name)
    file_bytes = _decode_uploaded_content(file_content_base64)
    result = _build_ingest_service().ingest_uploaded_file(file_name, file_bytes)
    return (
        f"Processed '{result.source_name}' successfully.\n"
        f"- raw_path: {result.raw_path}\n"
        f"- processed_path: {result.processed_path}\n"
        f"- metadata_path: {result.metadata_path}\n"
        f"- chunks_ingested: {result.chunk_count}"
    )
