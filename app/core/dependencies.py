from __future__ import annotations

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import AppError
from app.core.security import SESSION_COOKIE_NAME, read_session_token
from app.models.user import User


def get_current_user_optional(request: Request, db: Session = Depends(get_db)) -> User | None:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        return None
    user_id = read_session_token(token)
    if user_id is None:
        return None
    return db.get(User, user_id)


def get_current_user(user: User | None = Depends(get_current_user_optional)) -> User:
    if user is None:
        raise AppError(401, "AUTH_REQUIRED", "로그인이 필요합니다.")
    return user
