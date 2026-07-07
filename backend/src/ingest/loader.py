import os
from pathlib import Path

from backend.process_raw_data import process_service
from backend.src.core.models import DocumentRecord

_SUPPORTED_SUFFIXES = {".md", ".pdf", ".docx", ".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}


def _get_data_dir() -> Path:
    return Path(os.getenv("DATA_DIR", str(Path(__file__).parents[3] / "data" / "processed")))


class _DefaultLoaderProcessor:
    def process(self, file_path: Path) -> DocumentRecord | None:
        payload = process_service.process_file(file_path)
        if payload is None:
            return None
        return DocumentRecord.from_dict(payload)


def load_documents(config, sample_size=None, processor=None):
    documents = []
    document_processor = processor or _DefaultLoaderProcessor()
    data_dir = _get_data_dir()

    for file_path in sorted(data_dir.rglob("*")):
        if not file_path.is_file() or file_path.suffix.lower() not in _SUPPORTED_SUFFIXES:
            continue

        try:
            doc = document_processor.process(file_path)
        except Exception as exc:
            print(f"Warning: failed to process {file_path}: {exc}")
            continue

        if doc is None:
            continue

        document = DocumentRecord(
            content=doc.content,
            metadata={
                **doc.metadata,
                "relative_path": str(file_path.relative_to(data_dir)),
            },
        )
        documents.append(document.to_dict())

        if sample_size is not None and len(documents) >= sample_size:
            break

    return documents
