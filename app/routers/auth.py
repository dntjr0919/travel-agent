from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, Response
from sqlalchemy.orm import Session
from app.services.email_service import send_password_reset_email

from app.core.config import get_settings
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.security import SESSION_COOKIE_NAME, create_session_token
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    PasswordResetRequestResult,
    RegisterRequest,
    UserOut,
)
from app.services.auth_service import (
    authenticate_user,
    confirm_password_reset,
    register_user,
    request_password_reset,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])
settings = get_settings()


def _set_session_cookie(response: Response, user_id: int) -> None:
    token = create_session_token(user_id)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=settings.session_max_age_seconds,
        secure=False,  # 배포 시 HTTPS 환경에서는 True로 변경할 것
        path="/",
    )


@router.post("/register", response_model=UserOut, status_code=201)
def register(data: RegisterRequest, response: Response, db: Session = Depends(get_db)) -> User:
    user = register_user(db, data)
    _set_session_cookie(response, user.id)
    return user


@router.post("/login", response_model=UserOut)
def login(data: LoginRequest, response: Response, db: Session = Depends(get_db)) -> User:
    user = authenticate_user(db, data)
    _set_session_cookie(response, user.id)
    return user


@router.post("/logout", status_code=204, response_model=None)
def logout(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.post("/password-reset/request", response_model=PasswordResetRequestResult)
def request_reset(
    data: PasswordResetRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> PasswordResetRequestResult:
    reset_url = request_password_reset(db, data.email)

    if reset_url is not None:
        background_tasks.add_task(
            send_password_reset_email,
            data.email,
            reset_url,
        )

    return PasswordResetRequestResult(
        detail="해당 이메일로 가입된 계정이 있다면 비밀번호 재설정 링크를 발송했습니다.",
        reset_url=None,
    )


@router.post("/password-reset/confirm", response_model=UserOut)
def confirm_reset(data: PasswordResetConfirm, db: Session = Depends(get_db)) -> User:
    return confirm_password_reset(db, data.token, data.new_password)
