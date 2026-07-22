ARG APP_IMAGE_TAG=local
FROM agent-rag-app:${APP_IMAGE_TAG}

ENV MODEL_CORRECTION_VIETNAMESE_LOCAL=protonx-models/protonx-legal-tc \
    MODEL_CORRECTION_BACKEND=local \
    MODEL_CORRECTION_DEVICE=cpu

COPY . .

RUN --mount=type=secret,id=hf_token,required=false python - <<'PY'
from pathlib import Path

from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

model_id = "protonx-models/protonx-legal-tc"
cache_dir = "/opt/hf-cache"
token_path = Path("/run/secrets/hf_token")
token = token_path.read_text(encoding="utf-8").strip() if token_path.exists() else None
AutoTokenizer.from_pretrained(model_id, cache_dir=cache_dir, token=token)
AutoModelForSeq2SeqLM.from_pretrained(
    model_id,
    cache_dir=cache_dir,
    token=token,
    low_cpu_mem_usage=True,
)
print(f"Preloaded OCR correction model: {model_id}")
PY

ENTRYPOINT ["python", "-m", "backend.process_raw_data"]
