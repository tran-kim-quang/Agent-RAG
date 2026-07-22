FROM python:3.12-slim

WORKDIR /app

ENV HF_HOME=/opt/hf-cache \
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
 && poetry config installer.parallel false \
 && poetry install --no-root --no-interaction

ARG APP_BUILD_REV=dev
RUN printf '%s\n' "$APP_BUILD_REV" > /tmp/app_build_rev

COPY . .

RUN --mount=type=secret,id=hf_token,required=false python - <<'PY'
from pathlib import Path

from transformers import AutoModelForSequenceClassification, AutoTokenizer

cache_dir = "/opt/hf-cache"
token_path = Path("/run/secrets/hf_token")
token = token_path.read_text(encoding="utf-8").strip() if token_path.exists() else None
reranker_id = "BAAI/bge-reranker-v2-m3"
AutoTokenizer.from_pretrained(reranker_id, cache_dir=cache_dir, token=token)
AutoModelForSequenceClassification.from_pretrained(
    reranker_id,
    cache_dir=cache_dir,
    token=token,
    low_cpu_mem_usage=True,
)
print(f"Preloaded reranker model: {reranker_id}")
PY

ENTRYPOINT ["python", "-m", "backend.main"]
CMD ["interactive"]
