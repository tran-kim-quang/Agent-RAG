from pathlib import Path

from fastapi import HTTPException, UploadFile

SUPPORTED_TYPES = {
    ".md": {"text/markdown", "text/plain"}, ".pdf": {"application/pdf"},
    ".docx": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
    ".png": {"image/png"}, ".jpg": {"image/jpeg"}, ".jpeg": {"image/jpeg"},
    ".webp": {"image/webp"}, ".bmp": {"image/bmp", "image/x-ms-bmp"}, ".gif": {"image/gif"},
}


async def validate_upload(file: UploadFile, max_bytes: int) -> bytes:
    if not file.filename: raise HTTPException(status_code=400, detail="Uploaded file must have a filename.")
    suffix = Path(file.filename).suffix.lower()
    if suffix not in SUPPORTED_TYPES: raise HTTPException(status_code=415, detail="Unsupported file type.")
    if file.content_type and file.content_type != "application/octet-stream" and file.content_type not in SUPPORTED_TYPES[suffix]:
        raise HTTPException(status_code=415, detail="File content type does not match its extension.")
    content = await file.read(max_bytes + 1)
    if len(content) > max_bytes: raise HTTPException(status_code=413, detail=f"File exceeds the {max_bytes // 1024 // 1024} MB limit.")
    if not content: raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if not _matches_signature(suffix, content): raise HTTPException(status_code=415, detail="File content does not match its extension.")
    return content


def _matches_signature(suffix: str, content: bytes) -> bool:
    signatures = {".pdf": b"%PDF-", ".docx": b"PK\x03\x04", ".png": b"\x89PNG\r\n\x1a\n", ".jpg": b"\xff\xd8\xff", ".jpeg": b"\xff\xd8\xff", ".bmp": b"BM"}
    if suffix in signatures: return content.startswith(signatures[suffix])
    if suffix == ".gif": return content.startswith((b"GIF87a", b"GIF89a"))
    if suffix == ".webp": return len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP"
    if suffix == ".md":
        try: content.decode("utf-8"); return True
        except UnicodeDecodeError: return False
    return False
