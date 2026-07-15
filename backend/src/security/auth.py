from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from backend.src.core.repositories import RefreshTokenRepository, UserRepository
from backend.src.core.roles import UserRole
from backend.src.db import User


class TokenError(ValueError):
    pass


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str
    access_expires_in: int


class AuthService:
    def __init__(self, users: UserRepository, tokens: RefreshTokenRepository) -> None:
        self.users = users
        self.tokens = tokens
        self.secret = os.getenv("JWT_SECRET", "change-me-in-production")
        self.algorithm = "HS256"
        self.access_minutes = int(os.getenv("JWT_ACCESS_MINUTES", "15"))
        self.refresh_days = int(os.getenv("JWT_REFRESH_DAYS", "14"))
        self.password_hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4)

    def validate_runtime_config(self) -> None:
        if os.getenv("ENVIRONMENT", "development").lower() != "production":
            return
        if len(self.secret) < 32 or self.secret == "change-me-in-production":
            raise RuntimeError("JWT_SECRET must contain at least 32 characters in production.")
        required = ["DATABASE_URL", "REDIS_URL", "NEO4J_PASSWORD", "MINIO_ROOT_PASSWORD"]
        missing = [key for key in required if not os.getenv(key)]
        if missing:
            raise RuntimeError(f"Missing production configuration: {', '.join(missing)}")
        if os.getenv("COOKIE_SECURE", "false").lower() != "true":
            raise RuntimeError("COOKIE_SECURE must be true in production.")

    def register(self, email: str, password: str) -> User:
        normalized = self._normalize_email(email)
        self._validate_password(password)
        if self.users.get_by_email(normalized) is not None:
            raise ValueError("Email is already registered.")
        first_user_admin = (
            os.getenv("ENVIRONMENT", "development").lower() != "production"
            and os.getenv("ALLOW_FIRST_USER_ADMIN", "true").lower() == "true"
            and not self.users.list(limit=1)
        )
        role = UserRole.ADMIN if first_user_admin else UserRole.USER
        return self.users.create(normalized, self.password_hasher.hash(password), role=role)

    def ensure_bootstrap_admin(self) -> None:
        email = os.getenv("BOOTSTRAP_ADMIN_EMAIL", "").strip()
        password = os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "")
        if not email and not password:
            return
        if not email or not password:
            raise RuntimeError("BOOTSTRAP_ADMIN_EMAIL and BOOTSTRAP_ADMIN_PASSWORD must be configured together.")
        normalized = self._normalize_email(email)
        self._validate_password(password)
        if self.users.get_by_email(normalized) is None:
            self.users.create(normalized, self.password_hasher.hash(password), role=UserRole.ADMIN)

    def authenticate(self, email: str, password: str) -> User | None:
        try:
            normalized = self._normalize_email(email)
        except ValueError:
            return None
        user = self.users.get_by_email(normalized)
        if user is None or not user.is_active:
            return None
        try:
            self.password_hasher.verify(user.password_hash, password)
        except (VerifyMismatchError, InvalidHashError):
            return None
        return user

    def issue_token_pair(self, user: User) -> TokenPair:
        now = datetime.now(timezone.utc)
        access_seconds = self.access_minutes * 60
        access = jwt.encode(
            {
                "sub": user.id,
                "role": user.role,
                "type": "access",
                "iat": now,
                "exp": now + timedelta(seconds=access_seconds),
            },
            self.secret,
            algorithm=self.algorithm,
        )
        refresh_jti = uuid4().hex
        refresh_expiry = now + timedelta(days=self.refresh_days)
        refresh = jwt.encode(
            {
                "sub": user.id,
                "jti": refresh_jti,
                "type": "refresh",
                "iat": now,
                "exp": refresh_expiry,
            },
            self.secret,
            algorithm=self.algorithm,
        )
        self.tokens.save(user.id, self._hash_jti(refresh_jti), refresh_expiry)
        return TokenPair(access, refresh, access_seconds)

    def decode_access_token(self, token: str) -> User:
        payload = self._decode(token, "access")
        user = self.users.get(str(payload["sub"]))
        if user is None or not user.is_active:
            raise TokenError("User is inactive or no longer exists.")
        return user

    def rotate_refresh_token(self, token: str) -> TokenPair:
        payload = self._decode(token, "refresh")
        user_id = self.tokens.consume(self._hash_jti(str(payload.get("jti", ""))))
        user = self.users.get(user_id) if user_id else None
        if user is None or not user.is_active:
            raise TokenError("Refresh token has expired or was revoked.")
        return self.issue_token_pair(user)

    def revoke_refresh_token(self, token: str) -> None:
        try:
            payload = self._decode(token, "refresh")
        except TokenError:
            return
        self.tokens.revoke(self._hash_jti(str(payload.get("jti", ""))))

    def _decode(self, token: str, expected_type: str) -> dict:
        try:
            payload = jwt.decode(token, self.secret, algorithms=[self.algorithm])
        except jwt.PyJWTError as exc:
            raise TokenError("Token is invalid or expired.") from exc
        if payload.get("type") != expected_type or not payload.get("sub"):
            raise TokenError("Unexpected token type.")
        return payload

    @staticmethod
    def _hash_jti(jti: str) -> str:
        return hashlib.sha256(jti.encode("utf-8")).hexdigest()

    @staticmethod
    def _normalize_email(email: str) -> str:
        normalized = email.strip().lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", normalized):
            raise ValueError("A valid email address is required.")
        return normalized

    @staticmethod
    def _validate_password(password: str) -> None:
        if len(password) < 10 or not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
            raise ValueError("Password must be at least 10 characters and contain letters and numbers.")
