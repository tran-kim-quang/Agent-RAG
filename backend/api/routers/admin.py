from fastapi import APIRouter, HTTPException

from backend.api.dependencies import AdminUser, chat_runs, upload_jobs, users
from backend.api.presenters import clamp_limit, present_chat_session, present_upload, present_user
from backend.api.schemas import ChatSessionsResponse, UploadJobsResponse, UsersResponse

router = APIRouter(prefix="/api/admin")


@router.get("/users", response_model=UsersResponse)
def list_users(_: AdminUser, limit: int = 100) -> UsersResponse:
    return UsersResponse(users=[present_user(user) for user in users.list(clamp_limit(limit, 200))])


@router.get("/uploads", response_model=UploadJobsResponse)
def list_uploads(_: AdminUser, limit: int = 100, user_id: str | None = None) -> UploadJobsResponse:
    return _uploads(user_id, limit)


@router.get("/chat-sessions", response_model=ChatSessionsResponse)
def list_chats(_: AdminUser, limit: int = 100, user_id: str | None = None) -> ChatSessionsResponse:
    return _chats(user_id, limit)


@router.get("/users/{user_id}/uploads", response_model=UploadJobsResponse)
def user_uploads(user_id: str, _: AdminUser, limit: int = 100) -> UploadJobsResponse:
    _ensure_user(user_id); return _uploads(user_id, limit)


@router.get("/users/{user_id}/chat-sessions", response_model=ChatSessionsResponse)
def user_chats(user_id: str, _: AdminUser, limit: int = 100) -> ChatSessionsResponse:
    _ensure_user(user_id); return _chats(user_id, limit)


def _ensure_user(user_id: str) -> None:
    if users.get(user_id) is None: raise HTTPException(status_code=404, detail="User not found.")


def _uploads(user_id: str | None, limit: int) -> UploadJobsResponse:
    return UploadJobsResponse(jobs=[present_upload(job) for job in upload_jobs.list_upload_jobs(clamp_limit(limit, 200), user_id)])


def _chats(user_id: str | None, limit: int) -> ChatSessionsResponse:
    return ChatSessionsResponse(sessions=[present_chat_session(item) for item in chat_runs.list_chat_sessions(user_id, clamp_limit(limit, 200))])
