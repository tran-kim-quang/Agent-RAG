FROM python:3.12-slim

WORKDIR /app

ARG HF_TOKENS=""

ENV HF_HOME=/opt/hf-cache \
    MODEL_CORRECTION_VIETNAMESE_LOCAL=protonx-models/protonx-legal-tc \
    PIP_EXTRA_INDEX_URL=https://download.pytorch.org/whl/rocm6.3 \
    HF_TOKENS=${HF_TOKENS} \
    DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
    curl \
    poppler-utils \
    tesseract-ocr \
    tesseract-ocr-vie \
 && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir "poetry>=2.0.0,<3.0.0"

COPY pyproject.toml poetry.lock ./

RUN poetry config virtualenvs.create false \
 && poetry lock --no-interaction \
 && poetry install --no-root --no-interaction

RUN pip install --no-cache-dir --force-reinstall --no-deps \
    torch==2.7.1 \
    torchvision==0.22.1 \
    torchaudio==2.7.1 \
    --index-url https://download.pytorch.org/whl/rocm6.3

ARG APP_BUILD_REV=dev
RUN printf '%s\n' "$APP_BUILD_REV" > /tmp/app_build_rev

COPY . .

RUN python - <<'PY'
import os

from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

model_id = "protonx-models/protonx-legal-tc"
cache_dir = "/opt/hf-cache"
token = os.getenv("HF_TOKENS") or None
AutoTokenizer.from_pretrained(model_id, cache_dir=cache_dir, token=token)
AutoModelForSeq2SeqLM.from_pretrained(
    model_id,
    cache_dir=cache_dir,
    token=token,
    low_cpu_mem_usage=True,
)
print(f"Preloaded correction model: {model_id}")
PY

ENTRYPOINT ["python", "-m", "backend.process_raw_data"]
