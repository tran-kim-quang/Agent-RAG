import logging
import os
from threading import Lock

from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

_MODEL_LOCK = Lock()
_MODEL_BUNDLE = None


def _local_model_name() -> str:
    return (
        os.getenv("MODEL_CORRECTION_VIETNAMESE_LOCAL")
        or os.getenv("MODEL_CORRECTION_VIETNAMESE", "")
    ).split("#", 1)[0].strip()


def _load_local_bundle():
    global _MODEL_BUNDLE
    if _MODEL_BUNDLE is not None:
        return _MODEL_BUNDLE

    with _MODEL_LOCK:
        if _MODEL_BUNDLE is not None:
            return _MODEL_BUNDLE

        import torch
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

        model_name = _local_model_name()
        if not model_name:
            raise ValueError("MODEL_CORRECTION_VIETNAMESE_LOCAL is not configured.")

        hf_token = os.getenv("HF_TOKENS", "").strip() or None
        cache_dir = os.getenv("HF_HOME", "/opt/hf-cache")
        device = "cuda" if torch.cuda.is_available() else "cpu"

        logger.info(
            "[ocr/correction] Loading local correction model: model=%s device=%s cache_dir=%s",
            model_name,
            device,
            cache_dir,
        )

        tokenizer = AutoTokenizer.from_pretrained(
            model_name,
            token=hf_token,
            cache_dir=cache_dir,
        )
        model = AutoModelForSeq2SeqLM.from_pretrained(
            model_name,
            token=hf_token,
            cache_dir=cache_dir,
            low_cpu_mem_usage=True,
        )
        model.to(device)
        model.eval()

        _MODEL_BUNDLE = {
            "model_name": model_name,
            "tokenizer": tokenizer,
            "model": model,
            "device": device,
            "torch": torch,
        }
        logger.info(
            "[ocr/correction] Local correction model ready: model=%s device=%s",
            model_name,
            device,
        )
        return _MODEL_BUNDLE


def correct_vietnamese_ocr_text(text: str) -> str:
    cleaned = text.strip()
    if not cleaned:
        return cleaned

    if os.getenv("MODEL_CORRECTION_BACKEND", "local").strip().lower() != "local":
        return cleaned

    try:
        bundle = _load_local_bundle()
    except Exception as exc:
        logger.warning(
            "[ocr/correction] Could not load local correction model, using original OCR text: error=%s",
            exc,
        )
        return cleaned

    tokenizer = bundle["tokenizer"]
    model = bundle["model"]
    device = bundle["device"]
    torch = bundle["torch"]

    instruction = (
        "Hãy sửa lỗi chính tả và lỗi OCR cho đoạn văn tiếng Việt sau. "
        "Giữ nguyên ý nghĩa, không thêm thông tin mới."
    )
    prompt = f"{instruction}\n\n{cleaned}"

    try:
        inputs = tokenizer(
            prompt,
            return_tensors="pt",
            truncation=True,
            max_length=1024,
        )
        inputs = {key: value.to(device) for key, value in inputs.items()}

        with torch.inference_mode():
            output_ids = model.generate(
                **inputs,
                max_new_tokens=256,
                do_sample=False,
                num_beams=1,
            )

        generated = tokenizer.decode(output_ids[0], skip_special_tokens=True).strip()
        if generated.startswith(prompt):
            generated = generated[len(prompt):].strip(" \n:-")
        if generated.startswith(instruction):
            generated = generated[len(instruction):].strip(" \n:-")
        return generated or cleaned
    except Exception as exc:
        logger.warning(
            "[ocr/correction] Local correction inference failed, using original OCR text: error=%s",
            exc,
        )
        return cleaned
