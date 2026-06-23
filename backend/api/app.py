import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Lock
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from backend.api.schemas import (
    ChatRequest,
    ChatResponse,
    GraphDocumentResponse,
    GraphOverviewResponse,
    HealthResponse,
    UploadResponse,
    UploadStatusResponse,
)
from backend.src.agents.orchestrator import run as run_query
from backend.src.index.graph_index import get_document_graph, list_graph_documents
from backend.src.tools.processData_tool import process_and_ingest_uploaded_file

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Agent-RAG API", version="0.1.0")
executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="ingest-worker")
job_lock = Lock()
jobs: dict[str, dict] = {}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _create_job(file_name: str) -> dict:
    return {
        "job_id": uuid4().hex,
        "file_name": file_name,
        "status": "queued",
        "phase": "queued",
        "message": f"Queued '{file_name}' for background ingest.",
        "raw_path": None,
        "processed_path": None,
        "metadata_path": None,
        "chunk_count": None,
        "indexed_chunks": 0,
        "total_chunks": None,
        "source_name": None,
        "error": None,
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    }


def _update_job(job_id: str, **updates) -> None:
    with job_lock:
        job = jobs[job_id]
        job.update(updates)
        job["updated_at"] = _now_iso()


def _run_ingest_job(job_id: str, file_name: str, file_bytes: bytes) -> None:
    logger.info("[api/upload_job] Starting background ingest job: job_id=%s file_name=%s", job_id, file_name)
    _update_job(job_id, status="processing", phase="start", message=f"Started ingest for '{file_name}'.")

    def progress_callback(phase: str, message: str, details: dict | None = None) -> None:
        logger.info("[api/upload_job] Progress update: job_id=%s phase=%s message=%s", job_id, phase, message)
        updates = {
            "status": "processing",
            "phase": phase,
            "message": message,
        }
        if details:
            updates.update(details)
        _update_job(job_id, **updates)

    try:
        result = process_and_ingest_uploaded_file(
            file_name=file_name,
            file_bytes=file_bytes,
            progress_callback=progress_callback,
        )
        _update_job(
            job_id,
            status="completed",
            phase="done",
            message=f"Processed '{result['source_name']}' successfully.",
            raw_path=result["raw_path"],
            processed_path=result["processed_path"],
            metadata_path=result["metadata_path"],
            chunk_count=result["chunk_count"],
            indexed_chunks=result["chunk_count"],
            total_chunks=result["chunk_count"],
            source_name=result["source_name"],
        )
        logger.info("[api/upload_job] Background ingest completed: job_id=%s result=%s", job_id, result)
    except Exception as exc:
        logger.exception("[api/upload_job] Background ingest failed: job_id=%s file_name=%s", job_id, file_name)
        _update_job(
            job_id,
            status="failed",
            phase="failed",
            message=f"Document ingest failed for '{file_name}'.",
            error=str(exc),
        )


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.post("/api/chat", response_model=ChatResponse)
def chat(payload: ChatRequest) -> ChatResponse:
    try:
        logger.info("[api/chat] Incoming chat request: message=%s", payload.message)
        answer = run_query(payload.message)
        logger.info("[api/chat] Chat request completed successfully")
    except Exception as exc:
        logger.exception("[api/chat] Chat request failed")
        raise HTTPException(status_code=500, detail=f"Chat request failed: {exc}") from exc
    return ChatResponse(answer=answer)


@app.post("/api/documents/upload", response_model=UploadResponse)
async def upload_document(file: UploadFile = File(...)) -> UploadResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Uploaded file must have a filename.")

    try:
        logger.info("[api/upload] Incoming upload request: file_name=%s", file.filename)
        file_bytes = await file.read()
        logger.info("[api/upload] Upload payload read: file_name=%s size_bytes=%s", file.filename, len(file_bytes))

        job = _create_job(file.filename)
        with job_lock:
            jobs[job["job_id"]] = job
        executor.submit(_run_ingest_job, job["job_id"], file.filename, file_bytes)

        logger.info("[api/upload] Upload accepted and queued: job_id=%s file_name=%s", job["job_id"], file.filename)
        return UploadResponse(
            job_id=job["job_id"],
            status=job["status"],
            phase=job["phase"],
            message=job["message"],
        )
    except Exception as exc:
        logger.exception("[api/upload] Upload request failed: file_name=%s", file.filename)
        raise HTTPException(status_code=500, detail=f"Document ingest failed: {exc}") from exc


@app.get("/api/documents/upload/{job_id}", response_model=UploadStatusResponse)
def get_upload_status(job_id: str) -> UploadStatusResponse:
    with job_lock:
        job = jobs.get(job_id)

    if job is None:
        raise HTTPException(status_code=404, detail=f"Upload job not found: {job_id}")

    return UploadStatusResponse(**job)


@app.get("/api/graph/documents", response_model=GraphOverviewResponse)
def graph_documents(limit: int = 20) -> GraphOverviewResponse:
    return GraphOverviewResponse(documents=list_graph_documents(limit=limit))


@app.get("/api/graph/document", response_model=GraphDocumentResponse)
def graph_document(source: str, limit_chunks: int = 18) -> GraphDocumentResponse:
    payload = get_document_graph(source=source, limit_chunks=limit_chunks)
    return GraphDocumentResponse(**payload)
