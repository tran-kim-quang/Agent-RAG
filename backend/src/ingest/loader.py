from pathlib import Path

_DATA_DIR = Path("/home/meocon/work/Agent-RAG/data")

def load_documents(config, sample_size=None):
    documents = []

    for file_path in sorted(_DATA_DIR.rglob("*.md")):
        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = file_path.read_bytes().decode("utf-8", errors="replace")

        documents.append({
            "content": content,
            "metadata": {
                "source": str(file_path),
                "name": file_path.stem,
                "relative_path": str(file_path.relative_to(_DATA_DIR)),
            },
        })

        if sample_size is not None and len(documents) >= sample_size:
            break

    return documents