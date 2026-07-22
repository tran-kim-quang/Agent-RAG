import logging
import asyncio
import os

from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect
from redis.asyncio import Redis

from backend.api.dependencies import CurrentUser, auth_service, chat_runs, chats
from backend.api.presenters import clamp_limit, present_chat_session
from backend.api.rate_limit import enforce_rate_limit
from backend.api.schemas import ChatRequest, ChatResponse, ChatSessionResponse, ChatSessionsResponse
from backend.src.core.roles import is_admin
from backend.src.infrastructure.token_stream import token_stream_key
from backend.src.security import TokenError

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


@router.websocket("/{run_id}/stream")
async def stream_run(websocket: WebSocket, run_id: str) -> None:
    await websocket.accept()
    redis = Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"), decode_responses=True)
    try:
        auth_message = await asyncio.wait_for(websocket.receive_json(), timeout=10)
        if auth_message.get("type") != "authenticate" or not isinstance(auth_message.get("token"), str):
            await websocket.close(code=4401, reason="Authentication required")
            return
        try:
            user = await asyncio.to_thread(auth_service.decode_access_token, auth_message["token"])
        except TokenError:
            await websocket.close(code=4401, reason="Token is invalid or expired")
            return

        run = await asyncio.to_thread(chat_runs.get_chat_run, run_id, user.id, is_admin(user.role))
        if run is None:
            await websocket.close(code=4404, reason="Chat run not found")
            return

        await websocket.send_json({"type": "ready", "run_id": run_id})
        last_id = "0-0"
        while True:
            batches = await redis.xread({token_stream_key(run_id): last_id}, count=100, block=5000)
            if not batches:
                current = await asyncio.to_thread(chat_runs.get_chat_run, run_id, user.id, is_admin(user.role))
                if current and current["status"] == "completed":
                    await websocket.send_json({"type": "done", "answer": current.get("answer")})
                    return
                if current and current["status"] == "failed":
                    await websocket.send_json({"type": "error", "message": current.get("error") or "Chat run failed."})
                    return
                await websocket.send_json({"type": "heartbeat"})
                continue
            for _, events in batches:
                for event_id, fields in events:
                    last_id = event_id
                    if fields.get("type") == "done":
                        current = await asyncio.to_thread(chat_runs.get_chat_run, run_id, user.id, is_admin(user.role))
                        if current is not None:
                            fields = {**fields, "answer": current.get("answer")}
                    await websocket.send_json(fields)
                    if fields.get("type") in {"done", "error"}:
                        return
    except (asyncio.TimeoutError, WebSocketDisconnect):
        return
    finally:
        await redis.aclose()
