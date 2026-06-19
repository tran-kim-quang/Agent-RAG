import base64
import json
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


def _post_vision_request(prompt: str, image_b64: str, image_mime_type: str, system_prompt: str) -> str:
    payload = {
        "model": os.getenv("VISION_MODEL_NAME"),
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
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
    return _post_vision_request(
        (
            "Mô tả hình ảnh tài liệu này bằng tiếng Việt để phục vụ tìm kiếm. "
            "Ưu tiên các tiêu đề, đoạn chữ, nhãn, bảng biểu, sơ đồ và từ khóa."
        ),
        image_b64=image_b64,
        image_mime_type=image_mime_type,
        system_prompt=_SYSTEM_PROMPT,
    )


def describe_image_file(image_path: str | Path) -> str:
    path = Path(image_path)
    return describe_image_bytes(
        path.read_bytes(),
        mime_type=_detect_mime_type(path.name),
        image_name=path.name,
    )


def classify_document_page(
    image_bytes: bytes,
    mime_type: str | None = None,
    image_name: str | None = None,
) -> dict[str, str]:
    image_mime_type = mime_type or _detect_mime_type(image_name)
    image_b64 = base64.b64encode(image_bytes).decode("ascii")
    raw = _post_vision_request(
        (
            "Bạn đang phân loại một ảnh trang tài liệu. "
            "Hãy chọn đúng 1 nhãn: text_only, text_with_complex_visuals, visual_only_or_diagram. "
            'Trả về JSON dạng {"label":"...", "reason":"..."}.'
        ),
        image_b64=image_b64,
        image_mime_type=image_mime_type,
        system_prompt="You classify document page images. Return concise JSON only.",
    )
    try:
        data = json.loads(raw)
        label = str(data.get("label", "")).strip()
        reason = str(data.get("reason", "")).strip()
        if label:
            return {"label": label, "reason": reason}
    except json.JSONDecodeError:
        pass

    lowered = raw.lower()
    if "text_with_complex_visuals" in lowered:
        return {"label": "text_with_complex_visuals", "reason": raw}
    if "visual_only_or_diagram" in lowered:
        return {"label": "visual_only_or_diagram", "reason": raw}
    return {"label": "text_only", "reason": raw}


def describe_page_visuals(
    image_bytes: bytes,
    mime_type: str | None = None,
    image_name: str | None = None,
) -> str:
    image_mime_type = mime_type or _detect_mime_type(image_name)
    image_b64 = base64.b64encode(image_bytes).decode("ascii")
    return _post_vision_request(
        (
            "Đây là ảnh của một trang tài liệu PDF. "
            "Không cần chép lại toàn bộ chữ. "
            "Hãy tập trung mô tả sơ đồ, biểu đồ, bảng, hình minh họa, bố cục quan trọng "
            "và quan hệ giữa các thành phần bằng tiếng Việt."
        ),
        image_b64=image_b64,
        image_mime_type=image_mime_type,
        system_prompt="You describe the non-text visual content of document pages for retrieval.",
    )
