from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.security import hash_password, hash_token, verify_password
from app.models.password_reset import PasswordResetToken
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest

settings = get_settings()


def register_user(db: Session, data: RegisterRequest) -> User:
    existing = db.scalar(select(User).where(User.email == data.email))
    if existing is not None:
        raise AppError(409, "EMAIL_ALREADY_EXISTS", "이미 가입된 이메일입니다.")

    user = User(
        email=data.email,
        password_hash=hash_password(data.password),
        display_name=data.display_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, data: LoginRequest) -> User:
    user = db.scalar(select(User).where(User.email == data.email))
    if user is None or not verify_password(data.password, user.password_hash):
        raise AppError(401, "INVALID_CREDENTIALS", "이메일 또는 비밀번호가 올바르지 않습니다.")
    return user


def request_password_reset(db: Session, email: str) -> str | None:
    """토큰을 발급하고 개발용 재설정 링크를 반환한다. 계정이 없으면 None(이메일 존재 여부 비공개)."""
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        return None

    raw_token = secrets.token_urlsafe(32)
    reset_token = PasswordResetToken(
        user_id=user.id,
        token_hash=hash_token(raw_token),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=settings.password_reset_expire_minutes),
    )
    db.add(reset_token)
    db.commit()

    return f"{settings.app_base_url}/reset-password/{raw_token}"


def confirm_password_reset(db: Session, token: str, new_password: str) -> User:
    token_hash = hash_token(token)
    reset_token = db.scalar(select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash))
    if reset_token is None:
        raise AppError(404, "PASSWORD_RESET_TOKEN_INVALID", "유효하지 않은 재설정 링크입니다.")

    if reset_token.used_at is not None or reset_token.expires_at < datetime.now(timezone.utc):
        raise AppError(410, "PASSWORD_RESET_TOKEN_EXPIRED", "만료되었거나 이미 사용된 재설정 링크입니다.")

    user = db.get(User, reset_token.user_id)
    if user is None:
        raise AppError(404, "PASSWORD_RESET_TOKEN_INVALID", "유효하지 않은 재설정 링크입니다.")

    user.password_hash = hash_password(new_password)
    reset_token.used_at = datetime.now(timezone.utc)
    db.commit()
    return user
