import logging

from fastapi import APIRouter, HTTPException, Request

from backend.api.dependencies import CurrentUser, chat_runs, chats
from backend.api.presenters import clamp_limit, present_chat_session
from backend.api.rate_limit import enforce_rate_limit
from backend.api.schemas import ChatRequest, ChatResponse, ChatSessionResponse, ChatSessionsResponse
from backend.src.core.roles import is_admin

router = APIRouter(prefix="/api/chat")
logger = logging.getLogger(__name__)


@router.post("", response_model=ChatResponse, status_code=202)
def create(payload: ChatRequest, request: Request, user: CurrentUser) -> ChatResponse:
    enforce_rate_limit(request, "chat", user.id, 30, 60)
    try: return ChatResponse(**chat_runs.create_chat_run(payload.message, user.id, payload.chat_session_id))
    except PermissionError as exc: raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc: raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Could not enqueue chat request")
        raise HTTPException(status_code=503, detail="Chat queue is temporarily unavailable.") from exc


@router.get("/sessions", response_model=ChatSessionsResponse)
def list_sessions(user: CurrentUser, limit: int = 20) -> ChatSessionsResponse:
    return ChatSessionsResponse(sessions=[present_chat_session(item) for item in chat_runs.list_chat_sessions(user.id, clamp_limit(limit))])


@router.get("/sessions/{run_id}", response_model=ChatSessionResponse)
def get_session(run_id: str, user: CurrentUser) -> ChatSessionResponse:
    item = chats.get(run_id)
    if item is None or (not is_admin(user.role) and item.user_id != user.id): raise HTTPException(status_code=404, detail="Chat session not found.")
    return present_chat_session(item)


@router.get("/{run_id}", response_model=ChatResponse)
def get_status(run_id: str, user: CurrentUser) -> ChatResponse:
    run = chat_runs.get_chat_run(run_id, user.id, is_admin=is_admin(user.role))
    if run is None: raise HTTPException(status_code=404, detail="Chat run not found.")
    return ChatResponse(**run)
