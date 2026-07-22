from __future__ import annotations

import logging
import os
from functools import lru_cache
from threading import Lock
from typing import Protocol

logger = logging.getLogger(__name__)


class Reranker(Protocol):
    @property
    def model_name(self) -> str: ...

    def rerank(self, query: str, candidates: list[dict]) -> list[dict]: ...
    def warmup(self) -> None: ...


class IdentityReranker:
    @property
    def model_name(self) -> str:
        return "disabled"

    def rerank(self, _: str, candidates: list[dict]) -> list[dict]:
        return [dict(candidate) for candidate in candidates]

    def warmup(self) -> None:
        return None


class BgeCrossEncoderReranker:
    def __init__(
        self,
        model_name: str | None = None,
        top_n: int | None = None,
        batch_size: int | None = None,
        max_length: int | None = None,
        device: str | None = None,
    ) -> None:
        self._model_name = model_name or os.getenv("RERANKER_MODEL_NAME", "BAAI/bge-reranker-v2-m3")
        self._top_n = top_n or int(os.getenv("RERANKER_TOP_N", "5"))
        self._batch_size = batch_size or int(os.getenv("RERANKER_BATCH_SIZE", "8"))
        self._max_length = max_length or int(os.getenv("RERANKER_MAX_LENGTH", "512"))
        self._requested_device = device or os.getenv("RERANKER_DEVICE", "auto")
        self._load_lock = Lock()
        self._inference_lock = Lock()
        self._bundle: dict | None = None

    @property
    def model_name(self) -> str:
        return self._model_name

    def rerank(self, query: str, candidates: list[dict]) -> list[dict]:
        if not candidates:
            return []

        scores = self._score(query, [str(candidate.get("content", "")) for candidate in candidates])
        ranked = []
        for candidate, rerank_score in zip(candidates, scores):
            item = dict(candidate)
            item["retrieval_score"] = candidate.get("retrieval_score", candidate.get("score"))
            item["rerank_score"] = rerank_score
            item["score"] = rerank_score
            item["metadata"] = dict(candidate.get("metadata", {}))
            ranked.append(item)
        ranked.sort(key=lambda item: float(item["rerank_score"]), reverse=True)
        return ranked[: self._top_n]

    def warmup(self) -> None:
        self._load_bundle()

    def _score(self, query: str, passages: list[str]) -> list[float]:
        bundle = self._load_bundle()
        tokenizer = bundle["tokenizer"]
        model = bundle["model"]
        device = bundle["device"]
        torch = bundle["torch"]
        scores: list[float] = []

        with self._inference_lock, torch.inference_mode():
            for start in range(0, len(passages), self._batch_size):
                batch = passages[start : start + self._batch_size]
                inputs = tokenizer(
                    [[query, passage] for passage in batch],
                    padding=True,
                    truncation=True,
                    return_tensors="pt",
                    max_length=self._max_length,
                )
                inputs = {key: value.to(device) for key, value in inputs.items()}
                logits = model(**inputs, return_dict=True).logits.view(-1).float()
                scores.extend(torch.sigmoid(logits).cpu().tolist())
        return scores

    def _load_bundle(self) -> dict:
        if self._bundle is not None:
            return self._bundle
        with self._load_lock:
            if self._bundle is not None:
                return self._bundle

            import torch
            from transformers import AutoModelForSequenceClassification, AutoTokenizer

            device = self._resolve_device(torch)
            dtype = torch.float16 if device == "cuda" else torch.float32
            cache_dir = os.getenv("HF_HOME", "/opt/hf-cache")
            token = os.getenv("HF_TOKENS", "").strip() or None
            logger.info("Loading reranker model=%s device=%s", self._model_name, device)
            tokenizer = AutoTokenizer.from_pretrained(self._model_name, cache_dir=cache_dir, token=token)
            model = AutoModelForSequenceClassification.from_pretrained(
                self._model_name,
                cache_dir=cache_dir,
                token=token,
                dtype=dtype,
                low_cpu_mem_usage=True,
            )
            model.to(device)
            model.eval()
            self._bundle = {"tokenizer": tokenizer, "model": model, "device": device, "torch": torch}
            logger.info("Reranker ready: model=%s device=%s", self._model_name, device)
            return self._bundle

    def _resolve_device(self, torch) -> str:
        if self._requested_device == "auto":
            return "cuda" if torch.cuda.is_available() else "cpu"
        if self._requested_device == "cuda" and not torch.cuda.is_available():
            logger.warning("RERANKER_DEVICE=cuda but CUDA is unavailable; falling back to CPU")
            return "cpu"
        return self._requested_device


@lru_cache(maxsize=1)
def get_reranker() -> Reranker:
    if os.getenv("RERANKER_ENABLED", "true").lower() != "true":
        return IdentityReranker()
    return BgeCrossEncoderReranker()
