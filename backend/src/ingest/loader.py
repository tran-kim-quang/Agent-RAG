import os
from pathlib import Path

from backend.process_raw_data import process_service

_SUPPORTED_SUFFIXES = {".md", ".pdf", ".docx", ".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}


def _get_data_dir() -> Path:
    return Path(os.getenv("DATA_DIR", str(Path(__file__).parents[3] / "data" / "processed")))

def load_documents(config, sample_size=None):
    documents = []

    data_dir = _get_data_dir()

    for file_path in sorted(data_dir.rglob("*")):
        if not file_path.is_file() or file_path.suffix.lower() not in _SUPPORTED_SUFFIXES:
            continue

        try:
            doc = process_service.process_file(file_path)
        except Exception as exc:
            print(f"Warning: failed to process {file_path}: {exc}")
            continue

        if doc is None:
            continue

        doc["metadata"] = {
            **doc["metadata"],
            "relative_path": str(file_path.relative_to(data_dir)),
        }
        documents.append(doc)

        if sample_size is not None and len(documents) >= sample_size:
            break

    return documents
