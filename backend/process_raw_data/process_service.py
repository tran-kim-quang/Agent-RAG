import logging
import os
import re
import subprocess
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable
from xml.etree import ElementTree

from backend.process_raw_data.correct_service import correct_vietnamese_ocr_text
from backend.process_raw_data.ocr_service import extract_text_from_image
from backend.process_raw_data.vision_service import (
    classify_document_page,
    describe_image_bytes,
    describe_image_file,
    describe_page_visuals,
)
from backend.src.core.models import DocumentRecord
from backend.src.core.ports import ProgressCallback

_MARKDOWN_IMAGE_PATTERN = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")
_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}
logger = logging.getLogger(__name__)


def _get_pdf_reader_class():
    try:
        from pypdf import PdfReader
    except ModuleNotFoundError:
        return None

    return PdfReader


def _is_supported_image(path: Path) -> bool:
    return path.suffix.lower() in _IMAGE_SUFFIXES


def _append_image_understanding(content: str, sections: Iterable[str]) -> str:
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


def _extract_pdf_embedded_image_sections(
    page,
    page_number: int,
    max_images: int,
    min_image_bytes: int,
) -> tuple[list[str], int]:
    sections = []
    attempted = 0
    for image_index, image in enumerate(getattr(page, "images", []), start=1):
        if attempted >= max_images:
            break
        if len(image.data) < min_image_bytes:
            continue
        attempted += 1
        image_name = getattr(image, "name", None) or f"page-{page_number}-image-{image_index}.png"
        try:
            description = describe_image_bytes(image.data, image_name=image_name)
        except Exception:
            continue
        sections.append(_build_image_section(image_name, description))
    return sections, attempted


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


@dataclass(slots=True)
class PdfProcessingDependencies:
    read_page_text: Callable[[Path, int, object | None], str]
    render_page_to_image: Callable[[Path, int], tuple[str, bytes]]
    classify_page_image: Callable[[bytes, str | None], dict[str, str]]
    ocr_page_image: Callable[[bytes, str | None], str]
    correct_ocr_text: Callable[[str], str]
    describe_page_visuals: Callable[[bytes, str | None], str]
    describe_image_bytes_fn: Callable[..., str]


class BaseFileProcessor:
    supported_suffixes: set[str] = set()

    def supports(self, path: Path) -> bool:
        return path.suffix.lower() in self.supported_suffixes

    def process(self, path: Path, progress_callback: ProgressCallback | None = None) -> DocumentRecord:
        raise NotImplementedError


class MarkdownProcessor(BaseFileProcessor):
    supported_suffixes = {".md"}

    def process(self, path: Path, progress_callback: ProgressCallback | None = None) -> DocumentRecord:
        content = path.read_text(encoding="utf-8", errors="replace")
        image_sections = []

        for image_path in _resolve_markdown_image_paths(path, content):
            try:
                description = describe_image_file(image_path)
            except Exception:
                continue
            image_sections.append(_build_image_section(image_path.name, description))

        return DocumentRecord(
            content=_append_image_understanding(content, image_sections),
            metadata={
                "source": str(path),
                "name": path.stem,
                "source_type": "markdown",
            },
        )


class ImageProcessor(BaseFileProcessor):
    supported_suffixes = set(_IMAGE_SUFFIXES)

    def process(self, path: Path, progress_callback: ProgressCallback | None = None) -> DocumentRecord:
        description = describe_image_file(path)
        return DocumentRecord(
            content=_build_image_section(path.name, description),
            metadata={
                "source": str(path),
                "name": path.stem,
                "source_type": "image",
            },
        )


class PdfProcessor(BaseFileProcessor):
    supported_suffixes = {".pdf"}

    def __init__(self, dependencies: PdfProcessingDependencies | None = None) -> None:
        self._dependencies = dependencies or PdfProcessingDependencies(
            read_page_text=_extract_pdf_page_text,
            render_page_to_image=_render_pdf_page_to_image,
            classify_page_image=_classify_page_image_with_vlm,
            ocr_page_image=_ocr_page_image,
            correct_ocr_text=_correct_vietnamese_ocr_text,
            describe_page_visuals=_describe_page_visuals_with_vlm,
            describe_image_bytes_fn=describe_image_bytes,
        )

    def process(self, path: Path, progress_callback: ProgressCallback | None = None) -> DocumentRecord:
        reader_class = _get_pdf_reader_class()
        reader = reader_class(str(path)) if reader_class is not None else None
        page_count = _get_pdf_page_count(path, reader=reader)
        image_budget = max(0, int(os.getenv("PDF_MAX_EMBEDDED_IMAGES", "12")))
        min_image_bytes = max(0, int(os.getenv("PDF_MIN_EMBEDDED_IMAGE_BYTES", "8192")))
        sections = []
        for page_number in range(1, page_count + 1):
            page_sections, attempted_images = self._process_page(
                path,
                page_number,
                reader=reader,
                embedded_image_limit=image_budget,
                min_image_bytes=min_image_bytes,
            )
            image_budget -= attempted_images
            sections.extend(page_sections)
            if progress_callback is not None:
                progress_callback(
                    "process",
                    f"Processed PDF page {page_number} of {page_count}.",
                    {
                        "progress": 20 + int((page_number / page_count) * 14),
                        "current_page": page_number,
                        "total_pages": page_count,
                    },
                )

        return DocumentRecord(
            content="\n\n".join(section for section in sections if section.strip()),
            metadata={
                "source": str(path),
                "name": path.stem,
                "source_type": "pdf",
            },
        )

    def _process_page(
        self,
        pdf_path: Path,
        page_number: int,
        reader=None,
        embedded_image_limit: int = 0,
        min_image_bytes: int = 0,
    ) -> tuple[list[str], int]:
        page_text = self._dependencies.read_page_text(pdf_path, page_number, reader)
        if page_text:
            sections = [page_text]
            attempted_images = 0
            if reader is not None and embedded_image_limit > 0:
                image_sections, attempted_images = _extract_pdf_embedded_image_sections(
                    reader.pages[page_number - 1],
                    page_number,
                    embedded_image_limit,
                    min_image_bytes,
                )
                sections.extend(image_sections)
            return sections, attempted_images

        image_name, image_bytes = self._dependencies.render_page_to_image(pdf_path, page_number)
        try:
            classification = self._dependencies.classify_page_image(image_bytes, image_name)
        except Exception as exc:
            logger.warning(
                "[pdf/vision] Page classification failed; falling back to OCR: page=%s error=%s",
                page_number,
                exc,
            )
            classification = {"label": "text_only", "reason": "vision unavailable"}
        label = classification.get("label", "text_only")

        sections = []
        if label in {"text_only", "text_with_complex_visuals"}:
            ocr_text = self._dependencies.ocr_page_image(image_bytes, image_name)
            if ocr_text.strip():
                corrected_text = self._dependencies.correct_ocr_text(ocr_text)
                sections.append(_build_page_ocr_section(page_number, corrected_text))

        if label in {"text_with_complex_visuals", "visual_only_or_diagram"}:
            try:
                visual_description = self._dependencies.describe_page_visuals(image_bytes, image_name)
            except Exception as exc:
                logger.warning(
                    "[pdf/vision] Visual description failed; continuing without it: page=%s error=%s",
                    page_number,
                    exc,
                )
                visual_description = ""
            if visual_description.strip():
                sections.append(_build_page_visual_section(page_number, visual_description))

        return sections, 0


class DocxProcessor(BaseFileProcessor):
    supported_suffixes = {".docx"}

    def process(self, path: Path, progress_callback: ProgressCallback | None = None) -> DocumentRecord:
        text_content, image_sections = self._extract_text_and_images(path)
        return DocumentRecord(
            content=_append_image_understanding(text_content, image_sections),
            metadata={
                "source": str(path),
                "name": path.stem,
                "source_type": "docx",
            },
        )

    def _extract_text_and_images(self, docx_path: Path) -> tuple[str, list[str]]:
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


class DocumentProcessingService:
    def __init__(self, processors: Iterable[BaseFileProcessor] | None = None) -> None:
        self._processors = list(
            processors
            or [
                MarkdownProcessor(),
                ImageProcessor(),
                PdfProcessor(),
                DocxProcessor(),
            ]
        )

    def process(
        self,
        file_path: str | Path,
        progress_callback: ProgressCallback | None = None,
    ) -> DocumentRecord | None:
        path = Path(file_path)
        for processor in self._processors:
            if processor.supports(path):
                return processor.process(path, progress_callback)
        return None


def process_file(
    file_path: str | Path,
    progress_callback: ProgressCallback | None = None,
) -> dict | None:
    document = DocumentProcessingService().process(file_path, progress_callback)
    if document is None:
        return None
    return document.to_dict()
