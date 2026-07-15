from pathlib import Path
from typing import Callable

from backend.process_raw_data.process_service import DocumentProcessingService
from backend.src.index.graph_index import Neo4jGraphIndexer
from backend.src.ingest.chunker import SemanticDocumentChunker
from backend.src.ingest.cleaner import DefaultDocumentCleaner
from backend.src.ingest.service import LocalUploadedFileStorage, UploadedFileIngestService

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


def _build_ingest_service(owner_id: str = "system") -> UploadedFileIngestService:
    return UploadedFileIngestService(
        storage=LocalUploadedFileStorage(
            raw_data_dir=_RAW_DATA_DIR / owner_id,
            supported_suffixes=_SUPPORTED_SUFFIXES,
        ),
        processor=DocumentProcessingService(),
        cleaner=DefaultDocumentCleaner(),
        chunker=SemanticDocumentChunker(),
        graph_indexer=Neo4jGraphIndexer(owner_id=owner_id),
        processed_data_dir=_PROCESSED_DATA_DIR / owner_id,
    )


def process_and_ingest_uploaded_file(
    file_name: str,
    file_bytes: bytes,
    progress_callback: ProgressCallback | None = None,
    owner_id: str = "system",
) -> dict:
    result = _build_ingest_service(owner_id).ingest_uploaded_file(
        file_name=file_name,
        file_bytes=file_bytes,
        progress_callback=progress_callback,
    )
    return result.to_dict()
