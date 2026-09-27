from __future__ import annotations

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from passlib.context import CryptContext

from app.core.config import get_settings

settings = get_settings()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

_session_serializer = URLSafeTimedSerializer(settings.secret_key, salt="travel-planner-session")

SESSION_COOKIE_NAME = "session"


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    return pwd_context.verify(plain_password, password_hash)


def create_session_token(user_id: int) -> str:
    return _session_serializer.dumps({"user_id": user_id})


def read_session_token(token: str) -> int | None:
    """세션 쿠키를 검증하고 user_id를 반환한다. 무효하면 None."""
    try:
        data = _session_serializer.loads(token, max_age=settings.session_max_age_seconds)
    except (BadSignature, SignatureExpired):
        return None
    user_id = data.get("user_id")
    return int(user_id) if user_id is not None else None
