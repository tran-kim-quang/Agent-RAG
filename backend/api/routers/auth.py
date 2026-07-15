import os

from fastapi import APIRouter, HTTPException, Request, Response
from sqlalchemy.exc import IntegrityError

from backend.api.dependencies import CurrentUser, auth_service
from backend.api.presenters import present_user
from backend.api.rate_limit import client_identifier, enforce_rate_limit
from backend.api.schemas import AuthRequest, AuthResponse, MessageResponse, UserResponse
from backend.src.security import TokenError

router = APIRouter(prefix="/api")
REFRESH_COOKIE = "agent_rag_refresh"


@router.post("/auth/register", response_model=AuthResponse, status_code=201)
def register(payload: AuthRequest, request: Request, response: Response) -> AuthResponse:
    enforce_rate_limit(request, "register", client_identifier(request), 5, 3600)
    if os.getenv("ALLOW_REGISTRATION", "true").lower() != "true": raise HTTPException(status_code=403, detail="Registration is disabled.")
    try: user = auth_service.register(payload.email, payload.password)
    except IntegrityError as exc: raise HTTPException(status_code=409, detail="Email is already registered.") from exc
    except ValueError as exc: raise HTTPException(status_code=409 if "registered" in str(exc) else 400, detail=str(exc)) from exc
    return _issue(user, response)


@router.post("/auth/login", response_model=AuthResponse)
def login(payload: AuthRequest, request: Request, response: Response) -> AuthResponse:
    enforce_rate_limit(request, "login", client_identifier(request), 10, 300)
    user = auth_service.authenticate(payload.email, payload.password)
    if user is None: raise HTTPException(status_code=401, detail="Invalid email or password.")
    return _issue(user, response)


@router.post("/auth/refresh", response_model=AuthResponse)
def refresh(request: Request, response: Response) -> AuthResponse:
    enforce_rate_limit(request, "refresh", client_identifier(request), 30, 300)
    token = request.cookies.get(REFRESH_COOKIE)
    if not token: raise HTTPException(status_code=401, detail="Refresh token is missing.")
    try:
        pair = auth_service.rotate_refresh_token(token)
        user = auth_service.decode_access_token(pair.access_token)
    except TokenError as exc:
        _clear(response); raise HTTPException(status_code=401, detail=str(exc)) from exc
    _set(response, pair.refresh_token)
    return AuthResponse(access_token=pair.access_token, expires_in=pair.access_expires_in, user=present_user(user))


@router.post("/auth/logout", response_model=MessageResponse)
def logout(request: Request, response: Response) -> MessageResponse:
    token = request.cookies.get(REFRESH_COOKIE)
    if token: auth_service.revoke_refresh_token(token)
    _clear(response)
    return MessageResponse(message="Logged out.")


@router.get("/users/me", response_model=UserResponse)
def current_user(user: CurrentUser) -> UserResponse: return present_user(user)


def _issue(user, response: Response) -> AuthResponse:
    pair = auth_service.issue_token_pair(user); _set(response, pair.refresh_token)
    return AuthResponse(access_token=pair.access_token, expires_in=pair.access_expires_in, user=present_user(user))


def _set(response: Response, token: str) -> None:
    response.set_cookie(REFRESH_COOKIE, token, httponly=True, secure=os.getenv("COOKIE_SECURE", "false").lower() == "true", samesite="lax", max_age=auth_service.refresh_days * 86400, path="/api/auth")


def _clear(response: Response) -> None: response.delete_cookie(REFRESH_COOKIE, path="/api/auth")
