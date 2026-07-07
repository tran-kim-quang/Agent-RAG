import re
import unicodedata

from backend.src.core.models import DocumentRecord


def normalize_text(text: str) -> str:
    # Unicode NFC normalization (important for Vietnamese diacritics)
    text = unicodedata.normalize("NFC", text)

    # Strip markdown headings syntax but keep the text
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)

    # Remove markdown bold/italic markers
    text = re.sub(r"\*{1,3}(.+?)\*{1,3}", r"\1", text)
    text = re.sub(r"_{1,3}(.+?)_{1,3}", r"\1", text)

    # Remove markdown links, keep display text
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)

    # Remove markdown images
    text = re.sub(r"!\[[^\]]*\]\([^\)]+\)", "", text)

    # Remove inline code and code blocks
    text = re.sub(r"```[\s\S]*?```", "", text)
    text = re.sub(r"`[^`]+`", "", text)

    # Remove horizontal rules
    text = re.sub(r"^[-_*]{3,}\s*$", "", text, flags=re.MULTILINE)

    # Remove HTML tags (in case of mixed markdown/HTML)
    text = re.sub(r"<[^>]+>", " ", text)

    # Normalize whitespace: collapse multiple spaces/tabs into one
    text = re.sub(r"[ \t]+", " ", text)

    # Collapse more than 2 consecutive newlines
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


class DefaultDocumentCleaner:
    def clean(self, document: DocumentRecord) -> DocumentRecord:
        return DocumentRecord(
            content=normalize_text(document.content),
            metadata=dict(document.metadata),
        )


def clean_document(doc: dict) -> dict:
    return DefaultDocumentCleaner().clean(DocumentRecord.from_dict(doc)).to_dict()


def clean_documents(documents: list[dict]) -> list[dict]:
    return [clean_document(doc) for doc in documents]
