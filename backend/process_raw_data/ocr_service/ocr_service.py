import shutil
import subprocess
import tempfile
from pathlib import Path


def extract_text_from_image(
    image_bytes: bytes,
    image_name: str | None = None,
    languages: str = "vie+eng",
) -> str:
    if shutil.which("tesseract") is None:
        return ""

    suffix = Path(image_name or "page.png").suffix or ".png"
    with tempfile.TemporaryDirectory(prefix="agent_rag_ocr_") as temp_dir:
        image_path = Path(temp_dir) / f"input{suffix}"
        output_base = Path(temp_dir) / "output"
        image_path.write_bytes(image_bytes)

        result = subprocess.run(
            [
                "tesseract",
                str(image_path),
                str(output_base),
                "-l",
                languages,
                "--psm",
                "6",
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return ""

        output_path = output_base.with_suffix(".txt")
        if not output_path.exists():
            return ""
        return output_path.read_text(encoding="utf-8", errors="replace").strip()
