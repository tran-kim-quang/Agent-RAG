import base64
import mimetypes
import os
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

_SYSTEM_PROMPT = (
    "You describe document images for retrieval. Focus on visible text, headings, "
    "labels, diagrams, tables, and the most important visual details. "
    "Respond in Vietnamese."
)


def _detect_mime_type(image_name: str | None = None) -> str:
    if image_name:
        mime_type, _ = mimetypes.guess_type(image_name)
        if mime_type:
            return mime_type
    return "image/png"


def describe_image_bytes(
    image_bytes: bytes,
    mime_type: str | None = None,
    image_name: str | None = None,
) -> str:
    image_mime_type = mime_type or _detect_mime_type(image_name)
    image_b64 = base64.b64encode(image_bytes).decode("ascii")

    payload = {
        "model": os.getenv("VISION_MODEL_NAME"),
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Mô tả hình ảnh tài liệu này bằng tiếng Việt để phục vụ tìm kiếm. "
                            "Ưu tiên các tiêu đề, đoạn chữ, nhãn, bảng biểu, sơ đồ và từ khóa."
                        ),
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{image_mime_type};base64,{image_b64}"},
                    },
                ],
            },
        ],
        "temperature": 0.1,
    }

    headers = {
        "Authorization": f"Bearer {os.getenv('OLLAMA_API_KEY', '')}",
        "Content-Type": "application/json",
    }

    base_url = os.getenv("OLLAMA_BASE_URL", "https://ollama.com/v1").rstrip("/")
    response = requests.post(
        f"{base_url}/chat/completions",
        headers=headers,
        json=payload,
        timeout=120,
    )
    response.raise_for_status()
    data = response.json()
    return data["choices"][0]["message"]["content"].strip()


def describe_image_file(image_path: str | Path) -> str:
    path = Path(image_path)
    return describe_image_bytes(
        path.read_bytes(),
        mime_type=_detect_mime_type(path.name),
        image_name=path.name,
    )
