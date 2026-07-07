import logging

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
from backend.src.services import ChatRunService, GraphQueryService, UploadJobService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Agent-RAG API", version="0.1.0")

chat_run_service = ChatRunService()
graph_query_service = GraphQueryService()
upload_job_service = UploadJobService()


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
        run = chat_run_service.create_chat_run(payload.message)
    except Exception as exc:
        logger.exception("[api/chat] Chat request failed")
        raise HTTPException(status_code=500, detail=f"Chat request failed: {exc}") from exc
    return ChatResponse(
        run_id=run["run_id"],
        status=run["status"],
        message=run["message"],
        answer=run["answer"],
        error=run["error"],
        events=run["events"],
    )


@app.get("/api/chat/{run_id}", response_model=ChatResponse)
def get_chat_status(run_id: str) -> ChatResponse:
    run = chat_run_service.get_chat_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Chat run not found: {run_id}")
    return ChatResponse(
        run_id=run["run_id"],
        status=run["status"],
        message=run["message"],
        answer=run["answer"],
        error=run["error"],
        events=run["events"],
    )


@app.post("/api/documents/upload", response_model=UploadResponse)
async def upload_document(file: UploadFile = File(...)) -> UploadResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Uploaded file must have a filename.")

    try:
        logger.info("[api/upload] Incoming upload request: file_name=%s", file.filename)
        file_bytes = await file.read()
        logger.info("[api/upload] Upload payload read: file_name=%s size_bytes=%s", file.filename, len(file_bytes))

        job = upload_job_service.create_upload_job(file.filename, file_bytes)

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
    job = upload_job_service.get_upload_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Upload job not found: {job_id}")

    return UploadStatusResponse(**job)


@app.get("/api/graph/documents", response_model=GraphOverviewResponse)
def graph_documents(limit: int = 20) -> GraphOverviewResponse:
    return GraphOverviewResponse(documents=graph_query_service.list_documents(limit=limit))


@app.get("/api/graph/document", response_model=GraphDocumentResponse)
def graph_document(source: str, limit_chunks: int = 18) -> GraphDocumentResponse:
    payload = graph_query_service.get_document_graph(source=source, limit_chunks=limit_chunks)
    return GraphDocumentResponse(**payload)
