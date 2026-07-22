import logging
import os

from fastapi import APIRouter

from backend.api.dependencies import AdminUser, graph_queries, upload_jobs
from backend.api.schemas import HealthResponse, RuntimeConfig, RuntimeLog, RuntimeMetric, RuntimeStatusResponse

router = APIRouter(prefix="/api")
logger = logging.getLogger(__name__)


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse: return HealthResponse(status="ok")


@router.get("/status", response_model=RuntimeStatusResponse)
def status(_: AdminUser) -> RuntimeStatusResponse:
    graph_state = "Connected"
    try: graph_documents = graph_queries.list_documents(100, None)
    except Exception:
        logger.exception("Could not load graph documents"); graph_state, graph_documents = "Unavailable", []
    jobs = upload_jobs.list_upload_jobs(20, None)
    active = sum(job["status"] in {"queued", "processing", "retrying"} for job in jobs)
    failed = sum(job["status"] == "failed" for job in jobs)
    chunks = sum(int(document.get("indexed_chunks") or 0) for document in graph_documents)
    metrics = [
        RuntimeMetric(label="FastAPI", value="Online", detail="API process is responding.", tone="tertiary"),
        RuntimeMetric(label="Neo4j Graph", value=graph_state, detail=f"{len(graph_documents)} documents / {chunks} chunks", tone="secondary"),
        RuntimeMetric(label="Worker Queue", value=str(active), detail=f"{failed} failed upload jobs", tone="warning" if active or failed else "tertiary"),
        RuntimeMetric(label="PostgreSQL", value="Connected", detail="Persistent application state", tone="primary"),
    ]
    configs = [
        RuntimeConfig(key="LLM_MODEL_NAME", value=os.getenv("LLM_MODEL_NAME", "not set"), provider="Configured LLM"),
        RuntimeConfig(key="EMBEDDING_MODEL_NAME", value=os.getenv("EMBEDDING_MODEL_NAME", "not set"), provider="Ollama"),
        RuntimeConfig(key="OBJECT_STORAGE", value="MinIO", provider="S3-compatible self-hosted storage"),
    ]
    logs = [RuntimeLog(time=str(job["updated_at"]), level=str(job["status"]).upper(), message=str(job["message"])) for job in jobs[:10]] or [RuntimeLog(time="", level="INFO", message="No upload jobs recorded.")]
    return RuntimeStatusResponse(status="ok" if graph_state == "Connected" else "degraded", metrics=metrics, configs=configs, logs=logs)
