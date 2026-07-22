from backend.api.schemas import ChatMessageResponse, ChatSessionResponse, UploadStatusResponse, UserResponse
from backend.src.db import ChatSession, UploadJob, User


def present_user(user: User) -> UserResponse:
    return UserResponse(id=user.id, email=user.email, role=user.role, is_active=user.is_active, created_at=user.created_at.isoformat())


def present_chat_session(item: ChatSession) -> ChatSessionResponse:
    return ChatSessionResponse(
        run_id=item.id, user_id=item.user_id, title=item.title, status=item.status,
        answer=item.answer, error=item.error,
        messages=[ChatMessageResponse(id=m.id, role=m.role, content=m.content, created_at=m.created_at.isoformat()) for m in item.messages],
        created_at=item.created_at.isoformat(), updated_at=item.updated_at.isoformat(),
    )


def present_upload(job: dict) -> UploadStatusResponse:
    return UploadStatusResponse(**job)


def clamp_limit(value: int, maximum: int = 100) -> int:
    return min(max(value, 1), maximum)
