from pathlib import Path
from types import SimpleNamespace
import zipfile

from backend.process_raw_data import process_service
from backend.src.ingest import loader


def test_process_markdown_appends_local_image_understanding(tmp_path, monkeypatch):
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    image_path = docs_dir / "cover.png"
    image_path.write_bytes(b"fake-image")

    markdown_path = docs_dir / "note.md"
    markdown_path.write_text(
        "# Hello\n\nBefore image.\n\n![Cover](cover.png)\n\nAfter image.\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        process_service,
        "describe_image_file",
        lambda path: f"VISION:{Path(path).name}",
    )

    doc = process_service.process_file(markdown_path)

    assert doc is not None
    assert "Before image." in doc["content"]
    assert "After image." in doc["content"]
    assert "VISION:cover.png" in doc["content"]
    assert doc["metadata"]["source"] == str(markdown_path)


def test_process_image_file_uses_vision_description(tmp_path, monkeypatch):
    image_path = tmp_path / "diagram.jpg"
    image_path.write_bytes(b"jpeg-data")

    monkeypatch.setattr(
        process_service,
        "describe_image_file",
        lambda path: "A system design diagram with services and arrows.",
    )

    doc = process_service.process_file(image_path)

    assert doc is not None
    assert "system design diagram" in doc["content"]
    assert doc["metadata"]["source_type"] == "image"


def test_process_pdf_appends_image_understanding(monkeypatch, tmp_path):
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4")

    fake_pages = [
        SimpleNamespace(
            extract_text=lambda: "Page one text",
            images=[SimpleNamespace(name="page-1.jpg", data=b"img-1")],
        ),
        SimpleNamespace(
            extract_text=lambda: "Page two text",
            images=[],
        ),
    ]

    class FakeReader:
        def __init__(self, path):
            assert Path(path) == pdf_path
            self.pages = fake_pages

    monkeypatch.setattr(process_service, "_get_pdf_reader_class", lambda: FakeReader)
    monkeypatch.setattr(
        process_service,
        "describe_image_bytes",
        lambda image_bytes, mime_type=None, image_name=None: f"VISION:{image_name}",
    )

    doc = process_service.process_file(pdf_path)

    assert doc is not None
    assert "Page one text" in doc["content"]
    assert "Page two text" in doc["content"]
    assert "VISION:page-1.jpg" in doc["content"]
    assert doc["metadata"]["source_type"] == "pdf"


def test_load_documents_includes_supported_multimodal_files(tmp_path, monkeypatch):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    (raw_dir / "a.md").write_text("![img](a.png)", encoding="utf-8")
    (raw_dir / "a.png").write_bytes(b"image-bytes")

    monkeypatch.setenv("DATA_DIR", str(raw_dir))
    monkeypatch.setattr(
        process_service,
        "process_file",
        lambda path: {
            "content": f"processed:{path.name}",
            "metadata": {"source": str(path), "source_type": path.suffix.lstrip(".")},
        },
    )

    docs = loader.load_documents(config={})

    assert [Path(doc["metadata"]["source"]).name for doc in docs] == ["a.md", "a.png"]
    assert [doc["content"] for doc in docs] == ["processed:a.md", "processed:a.png"]


def test_process_docx_appends_image_understanding(tmp_path, monkeypatch):
    docx_path = tmp_path / "sample.docx"
    with zipfile.ZipFile(docx_path, "w") as archive:
        archive.writestr(
            "word/document.xml",
            (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                "<w:body><w:p><w:r><w:t>Hello DOCX</w:t></w:r></w:p></w:body>"
                "</w:document>"
            ),
        )
        archive.writestr("word/media/image1.png", b"png-bytes")

    monkeypatch.setattr(
        process_service,
        "describe_image_bytes",
        lambda image_bytes, mime_type=None, image_name=None: f"VISION:{image_name}",
    )

    doc = process_service.process_file(docx_path)

    assert doc is not None
    assert "Hello DOCX" in doc["content"]
    assert "VISION:image1.png" in doc["content"]
    assert doc["metadata"]["source_type"] == "docx"


def test_load_documents_skips_files_that_fail_processing(tmp_path, monkeypatch):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    (raw_dir / "a.md").write_text("hello", encoding="utf-8")
    (raw_dir / "b.png").write_bytes(b"image-bytes")

    monkeypatch.setenv("DATA_DIR", str(raw_dir))

    def fake_process_file(path):
        if path.suffix == ".png":
            raise RuntimeError("boom")
        return {
            "content": f"processed:{path.name}",
            "metadata": {"source": str(path), "source_type": path.suffix.lstrip(".")},
        }

    monkeypatch.setattr(process_service, "process_file", fake_process_file)

    docs = loader.load_documents(config={})

    assert len(docs) == 1
    assert docs[0]["content"] == "processed:a.md"
