import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree

from backend.process_raw_data.correct_service import correct_vietnamese_ocr_text
from backend.process_raw_data.ocr_service import extract_text_from_image
from backend.process_raw_data.vision_service import (
    classify_document_page,
    describe_image_bytes,
    describe_image_file,
    describe_page_visuals,
)

_MARKDOWN_IMAGE_PATTERN = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")
_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}


def _get_pdf_reader_class():
    try:
        from pypdf import PdfReader
    except ModuleNotFoundError:
        return None

    return PdfReader


def _is_supported_image(path: Path) -> bool:
    return path.suffix.lower() in _IMAGE_SUFFIXES


def _append_image_understanding(
    content: str,
    sections: Iterable[str],
) -> str:
    section_list = [section.strip() for section in sections if section and section.strip()]
    if not section_list:
        return content.strip()

    base = content.strip()
    joined = "\n\n".join(section_list)
    if not base:
        return joined
    return f"{base}\n\n{joined}"


def _build_image_section(label: str, description: str) -> str:
    return f"[Image understanding: {label}]\n{description.strip()}"


def _resolve_markdown_image_paths(markdown_path: Path, content: str) -> list[Path]:
    resolved_paths: list[Path] = []
    for raw_path in _MARKDOWN_IMAGE_PATTERN.findall(content):
        candidate = raw_path.strip()
        if not candidate or "://" in candidate or candidate.startswith("data:"):
            continue

        image_path = (markdown_path.parent / candidate).resolve()
        if image_path.exists() and image_path.is_file():
            resolved_paths.append(image_path)
    return resolved_paths


def _process_markdown(markdown_path: Path) -> dict:
    content = markdown_path.read_text(encoding="utf-8", errors="replace")
    image_sections = []

    for image_path in _resolve_markdown_image_paths(markdown_path, content):
        try:
            description = describe_image_file(image_path)
        except Exception:
            continue
        image_sections.append(_build_image_section(image_path.name, description))

    return {
        "content": _append_image_understanding(content, image_sections),
        "metadata": {
            "source": str(markdown_path),
            "name": markdown_path.stem,
            "source_type": "markdown",
        },
    }


def _process_image(image_path: Path) -> dict:
    description = describe_image_file(image_path)
    return {
        "content": _build_image_section(image_path.name, description),
        "metadata": {
            "source": str(image_path),
            "name": image_path.stem,
            "source_type": "image",
        },
    }


def _extract_pdf_image_sections(pdf_path: Path) -> tuple[str, list[str]]:
    PdfReader = _get_pdf_reader_class()
    if PdfReader is None:
        return _extract_pdf_with_poppler(pdf_path)

    reader = PdfReader(str(pdf_path))

    page_texts = []
    image_sections = []

    for page_number, page in enumerate(reader.pages, start=1):
        text = ""
        if hasattr(page, "extract_text"):
            text = page.extract_text() or ""
        if text.strip():
            page_texts.append(text.strip())

        for image_index, image in enumerate(getattr(page, "images", []), start=1):
            image_name = getattr(image, "name", None) or f"pa   ge-{page_number}-image-{image_index}.png"
            try:
                description = describe_image_bytes(
                    image.data,
                    image_name=image_name,
                )
            except Exception:
                continue
            image_sections.append(_build_image_section(image_name, description))

    return "\n\n".join(page_texts), image_sections


def _extract_pdf_page_text(pdf_path: Path, page_number: int, reader=None) -> str:
    if reader is not None:
        page = reader.pages[page_number - 1]
        if hasattr(page, "extract_text"):
            return (page.extract_text() or "").strip()

    result = subprocess.run(
        ["pdftotext", "-f", str(page_number), "-l", str(page_number), str(pdf_path), "-"],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _render_pdf_page_to_image(pdf_path: Path, page_number: int) -> tuple[str, bytes]:
    with tempfile.TemporaryDirectory(prefix="agent_rag_pdf_page_") as temp_dir:
        output_base = Path(temp_dir) / f"page-{page_number}"
        subprocess.run(
            [
                "pdftoppm",
                "-f",
                str(page_number),
                "-l",
                str(page_number),
                "-png",
                "-singlefile",
                str(pdf_path),
                str(output_base),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        image_path = output_base.with_suffix(".png")
        return image_path.name, image_path.read_bytes()


def _classify_page_image_with_vlm(image_bytes: bytes, image_name: str | None = None) -> dict[str, str]:
    return classify_document_page(image_bytes, image_name=image_name)


def _ocr_page_image(image_bytes: bytes, image_name: str | None = None) -> str:
    return extract_text_from_image(image_bytes, image_name=image_name)


def _correct_vietnamese_ocr_text(text: str) -> str:
    return correct_vietnamese_ocr_text(text)


def _describe_page_visuals_with_vlm(image_bytes: bytes, image_name: str | None = None) -> str:
    return describe_page_visuals(image_bytes, image_name=image_name)


def _build_page_ocr_section(page_number: int, text: str) -> str:
    return f"[Page OCR: {page_number}]\n{text.strip()}"


def _build_page_visual_section(page_number: int, description: str) -> str:
    return f"[Page visual understanding: {page_number}]\n{description.strip()}"


def _extract_pdf_embedded_image_sections(page, page_number: int) -> list[str]:
    sections = []
    for image_index, image in enumerate(getattr(page, "images", []), start=1):
        image_name = getattr(image, "name", None) or f"page-{page_number}-image-{image_index}.png"
        try:
            description = describe_image_bytes(image.data, image_name=image_name)
        except Exception:
            continue
        sections.append(_build_image_section(image_name, description))
    return sections


def _get_pdf_page_count(pdf_path: Path, reader=None) -> int:
    if reader is not None:
        return len(reader.pages)

    result = subprocess.run(
        ["pdfinfo", str(pdf_path)],
        capture_output=True,
        text=True,
        check=True,
    )
    for line in result.stdout.splitlines():
        if line.startswith("Pages:"):
            return int(line.split(":", 1)[1].strip())
    raise ValueError(f"Could not determine page count for {pdf_path}")


def _process_pdf_page(pdf_path: Path, page_number: int, reader=None) -> list[str]:
    page_text = _extract_pdf_page_text(pdf_path, page_number, reader=reader)
    if page_text:
        sections = [page_text]
        if reader is not None:
            sections.extend(_extract_pdf_embedded_image_sections(reader.pages[page_number - 1], page_number))
        return sections

    image_name, image_bytes = _render_pdf_page_to_image(pdf_path, page_number)
    classification = _classify_page_image_with_vlm(image_bytes, image_name=image_name)
    label = classification.get("label", "text_only")

    sections = []
    if label in {"text_only", "text_with_complex_visuals"}:
        ocr_text = _ocr_page_image(image_bytes, image_name=image_name)
        if ocr_text.strip():
            corrected_text = _correct_vietnamese_ocr_text(ocr_text)
            sections.append(_build_page_ocr_section(page_number, corrected_text))

    if label in {"text_with_complex_visuals", "visual_only_or_diagram"}:
        visual_description = _describe_page_visuals_with_vlm(image_bytes, image_name=image_name)
        if visual_description.strip():
            sections.append(_build_page_visual_section(page_number, visual_description))

    return sections


def _extract_pdf_with_poppler(pdf_path: Path) -> tuple[str, list[str]]:
    text_result = subprocess.run(
        ["pdftotext", str(pdf_path), "-"],
        capture_output=True,
        text=True,
        check=True,
    )
    text_content = text_result.stdout.strip()

    image_sections = []
    with tempfile.TemporaryDirectory(prefix="agent_rag_pdf_") as temp_dir:
        prefix = Path(temp_dir) / "image"
        subprocess.run(
            ["pdfimages", "-j", str(pdf_path), str(prefix)],
            capture_output=True,
            text=True,
            check=True,
        )

        for image_path in sorted(Path(temp_dir).glob("image-*")):
            if not image_path.is_file():
                continue
            try:
                description = describe_image_file(image_path)
            except Exception:
                continue
            image_sections.append(_build_image_section(image_path.name, description))

    return text_content, image_sections


def _process_pdf(pdf_path: Path) -> dict:
    PdfReader = _get_pdf_reader_class()
    reader = PdfReader(str(pdf_path)) if PdfReader is not None else None
    page_count = _get_pdf_page_count(pdf_path, reader=reader)
    sections = []
    for page_number in range(1, page_count + 1):
        sections.extend(_process_pdf_page(pdf_path, page_number, reader=reader))

    return {
        "content": "\n\n".join(section for section in sections if section.strip()),
        "metadata": {
            "source": str(pdf_path),
            "name": pdf_path.stem,
            "source_type": "pdf",
        },
    }


def _extract_docx_text_and_images(docx_path: Path) -> tuple[str, list[str]]:
    with zipfile.ZipFile(docx_path) as archive:
        document_xml = archive.read("word/document.xml")
        root = ElementTree.fromstring(document_xml)
        namespaces = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}

        paragraphs = []
        for paragraph in root.findall(".//w:p", namespaces):
            texts = [node.text for node in paragraph.findall(".//w:t", namespaces) if node.text]
            paragraph_text = "".join(texts).strip()
            if paragraph_text:
                paragraphs.append(paragraph_text)

        image_sections = []
        for member in archive.namelist():
            if not member.startswith("word/media/"):
                continue
            image_name = Path(member).name
            image_bytes = archive.read(member)
            try:
                description = describe_image_bytes(image_bytes, image_name=image_name)
            except Exception:
                continue
            image_sections.append(_build_image_section(image_name, description))

    return "\n\n".join(paragraphs), image_sections


def _process_docx(docx_path: Path) -> dict:
    text_content, image_sections = _extract_docx_text_and_images(docx_path)
    return {
        "content": _append_image_understanding(text_content, image_sections),
        "metadata": {
            "source": str(docx_path),
            "name": docx_path.stem,
            "source_type": "docx",
        },
    }


def process_file(file_path: str | Path) -> dict | None:
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix == ".md":
        return _process_markdown(path)
    if _is_supported_image(path):
        return _process_image(path)
    if suffix == ".pdf":
        return _process_pdf(path)
    if suffix == ".docx":
        return _process_docx(path)
    return None
