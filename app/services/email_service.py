from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def _validate_smtp_settings() -> None:
    """이메일 발송이 활성화된 경우 필수 SMTP 설정을 확인한다."""
    required_values = {
        "SMTP_HOST": settings.smtp_host,
        "SMTP_FROM_EMAIL": settings.smtp_from_email,
    }

    if settings.smtp_username:
        required_values["SMTP_PASSWORD"] = settings.smtp_password

    missing_keys = [key for key, value in required_values.items() if not value]

    if missing_keys:
        missing_text = ", ".join(missing_keys)
        raise RuntimeError(f"SMTP 설정이 비어 있습니다: {missing_text}")


def send_password_reset_email(to_email: str, reset_url: str) -> None:
    """비밀번호 재설정 링크를 실제 이메일로 발송한다."""
    if not settings.email_enabled:
        logger.info("EMAIL_ENABLED=false 이므로 비밀번호 재설정 메일을 보내지 않습니다.")
        return

    _validate_smtp_settings()

    message = EmailMessage()
    message["Subject"] = "[Travel Planner] 비밀번호 재설정"
    message["From"] = f"{settings.smtp_from_name} <{settings.smtp_from_email}>"
    message["To"] = to_email

    message.set_content(
        f"""안녕하세요.

Travel Planner 비밀번호 재설정 요청이 접수되었습니다.

아래 링크를 열어 새 비밀번호를 설정하세요.

{reset_url}

이 링크는 {settings.password_reset_expire_minutes}분 동안 유효합니다.

본인이 요청하지 않았다면 이 이메일을 무시하세요.
"""
    )

    with smtplib.SMTP(
        host=settings.smtp_host,
        port=settings.smtp_port,
        timeout=15,
    ) as server:
        if settings.smtp_use_tls:
            server.starttls()

        if settings.smtp_username:
            server.login(
                settings.smtp_username,
                settings.smtp_password,
            )

        server.send_message(message)

    logger.info("비밀번호 재설정 이메일 발송 완료: %s", to_email)