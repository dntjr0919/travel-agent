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

    try:
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
            local_hostname="localhost",
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

    except Exception:
        logger.exception("비밀번호 재설정 이메일 발송 실패: %s", to_email)


def send_invitation_email(
    to_email: str,
    invite_url: str,
    trip_title: str,
    inviter_name: str,
    role: str,
) -> None:
    """여행 공동 작업 초대 링크를 이메일로 발송한다. 실패해도 예외를 전파하지 않는다."""
    if not settings.email_enabled:
        logger.info("EMAIL_ENABLED=false 이므로 초대 이메일을 보내지 않습니다.")
        return

    try:
        _send_invitation_email(to_email, invite_url, trip_title, inviter_name, role)
    except Exception:
        logger.exception("여행 초대 이메일 발송 실패: %s", to_email)


def _send_invitation_email(
    to_email: str,
    invite_url: str,
    trip_title: str,
    inviter_name: str,
    role: str,
) -> None:
    _validate_smtp_settings()

    role_label = {
        "editor": "편집자",
        "viewer": "조회자",
    }.get(role, role)

    message = EmailMessage()
    message["Subject"] = f"[Travel Planner] {trip_title} 여행 초대"
    message["From"] = f"{settings.smtp_from_name} <{settings.smtp_from_email}>"
    message["To"] = to_email

    message.set_content(
        f"""안녕하세요.

{inviter_name}님이 Travel Planner의 여행에 초대했습니다.

여행: {trip_title}
권한: {role_label}

아래 링크를 열어 초대를 수락하세요.

{invite_url}

초대 링크는 {settings.invitation_expire_hours}시간 동안 유효합니다.

본인이 예상하지 못한 초대라면 이 이메일을 무시하세요.
"""
    )

    with smtplib.SMTP(
        host=settings.smtp_host,
        port=settings.smtp_port,
        local_hostname="localhost",
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

    logger.info("여행 초대 이메일 발송 완료: %s", to_email)    