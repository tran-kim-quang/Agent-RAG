import os

import requests
from dotenv import load_dotenv

load_dotenv()


def correct_vietnamese_ocr_text(text: str) -> str:
    cleaned = text.strip()
    if not cleaned:
        return cleaned

    model_name = os.getenv("MODEL_CORRECTION_VIETNAMESE", "").split("#", 1)[0].strip()
    hf_token = os.getenv("HF_TOKENS", "").strip()
    if not model_name or not hf_token:
        return cleaned

    prompt = (
        "Hãy sửa lỗi chính tả và lỗi OCR cho đoạn văn tiếng Việt sau. "
        "Giữ nguyên ý nghĩa, không thêm thông tin mới.\n\n"
        f"{cleaned}"
    )
    response = requests.post(
        f"https://api-inference.huggingface.co/models/{model_name}",
        headers={"Authorization": f"Bearer {hf_token}"},
        json={"inputs": prompt, "options": {"wait_for_model": True}},
        timeout=120,
    )
    if response.status_code >= 400:
        return cleaned

    data = response.json()
    if isinstance(data, list) and data and isinstance(data[0], dict):
        generated = data[0].get("generated_text", "").strip()
        return generated or cleaned
    if isinstance(data, dict):
        generated = (data.get("generated_text") or data.get("summary_text") or "").strip()
        return generated or cleaned
    return cleaned
