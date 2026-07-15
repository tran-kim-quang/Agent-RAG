import logging
import os
from io import BytesIO
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse

from backend.api.dependencies import CurrentUser, upload_jobs
from backend.api.presenters import clamp_limit, present_upload
from backend.api.rate_limit import enforce_rate_limit
from backend.api.schemas import UploadJobsResponse, UploadResponse, UploadStatusResponse
from backend.api.upload_validation import validate_upload
from backend.src.core.roles import is_admin

router = APIRouter(prefix="/api/documents")
logger = logging.getLogger(__name__)
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_MB", "25")) * 1024 * 1024


@router.post("/upload", response_model=UploadResponse, status_code=202)
async def upload(request: Request, user: CurrentUser, file: UploadFile = File(...)) -> UploadResponse:
    enforce_rate_limit(request, "upload", user.id, 20, 3600)
    content = await validate_upload(file, MAX_UPLOAD_BYTES)
    try: return UploadResponse(**upload_jobs.create_upload_job(file.filename or "", content, user.id, file.content_type))
    except Exception as exc:
        logger.exception("Could not store or enqueue upload")
        raise HTTPException(status_code=503, detail="Upload storage or queue is temporarily unavailable.") from exc


@router.get("/uploads", response_model=UploadJobsResponse)
def list_jobs(user: CurrentUser, limit: int = 20) -> UploadJobsResponse:
    return UploadJobsResponse(jobs=[present_upload(job) for job in upload_jobs.list_upload_jobs(clamp_limit(limit), user.id)])


@router.get("/upload/{job_id}", response_model=UploadStatusResponse)
def get_job(job_id: str, user: CurrentUser) -> UploadStatusResponse:
    job = upload_jobs.get_upload_job(job_id, user.id, is_admin=is_admin(user.role))
    if job is None: raise HTTPException(status_code=404, detail="Upload job not found.")
    return present_upload(job)


@router.get("/upload/{job_id}/download")
def download(job_id: str, user: CurrentUser) -> StreamingResponse:
    result = upload_jobs.get_download(job_id, user.id, is_admin=is_admin(user.role))
    if result is None: raise HTTPException(status_code=404, detail="Upload object not found.")
    payload, name, content_type = result
    return StreamingResponse(BytesIO(payload), media_type=content_type, headers={"Content-Disposition": f'attachment; filename="{Path(name).name}"'})
