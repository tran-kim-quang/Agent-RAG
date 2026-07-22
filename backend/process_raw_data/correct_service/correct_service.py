from __future__ import annotations

import gc
import logging
import os
from functools import lru_cache
from threading import Lock, Timer
from typing import Protocol

from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


class OcrCorrector(Protocol):
    def correct(self, text: str) -> str: ...


class PassthroughOcrCorrector:
    def correct(self, text: str) -> str:
        return text.strip()


class LocalVietnameseOcrCorrector:
    def __init__(
        self,
        model_name: str | None = None,
        device: str | None = None,
        idle_seconds: float | None = None,
    ) -> None:
        configured_model = model_name or os.getenv("MODEL_CORRECTION_VIETNAMESE_LOCAL") or os.getenv(
            "MODEL_CORRECTION_VIETNAMESE", ""
        )
        self._model_name = configured_model.split("#", 1)[0].strip()
        self._requested_device = device or os.getenv("MODEL_CORRECTION_DEVICE", "cpu")
        self._idle_seconds = idle_seconds if idle_seconds is not None else int(
            os.getenv("MODEL_CORRECTION_IDLE_SECONDS", "300")
        )
        self._load_lock = Lock()
        self._inference_lock = Lock()
        self._bundle: dict | None = None
        self._unload_timer: Timer | None = None

    def correct(self, text: str) -> str:
        cleaned = text.strip()
        if not cleaned:
            return cleaned
        with self._load_lock:
            if self._unload_timer is not None:
                self._unload_timer.cancel()
                self._unload_timer = None

        try:
            bundle = self._load_bundle()
            corrected = self._run_inference(cleaned, bundle)
            return corrected or cleaned
        except Exception as exc:
            logger.warning(
                "[ocr/correction] Local correction failed, using original OCR text: error=%s",
                exc,
            )
            return cleaned
        finally:
            self._schedule_unload()

    def unload(self) -> None:
        with self._inference_lock, self._load_lock:
            if self._unload_timer is not None:
                self._unload_timer.cancel()
            self._bundle = None
            self._unload_timer = None
        gc.collect()
        logger.info("[ocr/correction] Released correction model from memory")

    def _load_bundle(self) -> dict:
        if self._bundle is not None:
            return self._bundle
        with self._load_lock:
            if self._bundle is not None:
                return self._bundle
            if not self._model_name:
                raise ValueError("MODEL_CORRECTION_VIETNAMESE is not configured.")

            import torch
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

            device = self._resolve_device(torch)
            cache_dir = os.getenv("HF_HOME", "/opt/hf-cache")
            token = os.getenv("HF_TOKENS", "").strip() or None
            logger.info(
                "[ocr/correction] Loading local correction model: model=%s device=%s cache_dir=%s",
                self._model_name,
                device,
                cache_dir,
            )
            tokenizer = AutoTokenizer.from_pretrained(self._model_name, token=token, cache_dir=cache_dir)
            model = AutoModelForSeq2SeqLM.from_pretrained(
                self._model_name,
                token=token,
                cache_dir=cache_dir,
                low_cpu_mem_usage=True,
            )
            model.to(device)
            model.eval()
            self._bundle = {
                "tokenizer": tokenizer,
                "model": model,
                "device": device,
                "torch": torch,
            }
            logger.info(
                "[ocr/correction] Local correction model ready: model=%s device=%s",
                self._model_name,
                device,
            )
            return self._bundle

    def _run_inference(self, text: str, bundle: dict) -> str:
        instruction = (
            "Hãy sửa lỗi chính tả và lỗi OCR cho đoạn văn tiếng Việt sau. "
            "Giữ nguyên ý nghĩa, không thêm thông tin mới."
        )
        prompt = f"{instruction}\n\n{text}"
        tokenizer = bundle["tokenizer"]
        model = bundle["model"]
        torch = bundle["torch"]
        with self._inference_lock:
            inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=1024)
            inputs = {key: value.to(bundle["device"]) for key, value in inputs.items()}
            with torch.inference_mode():
                output_ids = model.generate(
                    **inputs,
                    max_new_tokens=256,
                    do_sample=False,
                    num_beams=1,
                )
            generated = tokenizer.decode(output_ids[0], skip_special_tokens=True).strip()
        if generated.startswith(prompt):
            generated = generated[len(prompt) :].strip(" \n:-")
        if generated.startswith(instruction):
            generated = generated[len(instruction) :].strip(" \n:-")
        return generated

    def _resolve_device(self, torch) -> str:
        if self._requested_device == "cuda" and not torch.cuda.is_available():
            logger.warning("Correction CUDA device is unavailable; falling back to CPU")
            return "cpu"
        return self._requested_device

    def _schedule_unload(self) -> None:
        with self._load_lock:
            if self._unload_timer is not None:
                self._unload_timer.cancel()
            if self._idle_seconds <= 0:
                self._unload_timer = None
                return
            self._unload_timer = Timer(self._idle_seconds, self.unload)
            self._unload_timer.daemon = True
            self._unload_timer.start()


@lru_cache(maxsize=1)
def get_ocr_corrector() -> OcrCorrector:
    if os.getenv("MODEL_CORRECTION_BACKEND", "local").strip().lower() != "local":
        return PassthroughOcrCorrector()
    return LocalVietnameseOcrCorrector()


def correct_vietnamese_ocr_text(text: str) -> str:
    return get_ocr_corrector().correct(text)
