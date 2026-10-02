from __future__ import annotations

import json
import logging
from datetime import datetime
from urllib.parse import urlparse

from app.core.config import DEFAULT_RESERVATION_ANALYSIS_MODEL, RESERVATION_ANALYSIS_MODEL_NAMES
from app.core.errors import AppError
from app.schemas.reservation_import import DEFAULT_WARNING, TIMEZONE_FALLBACK_WARNING, ReservationImportAnalyzeOut
from app.services.llm import get_gemini_reservation_json

logger = logging.getLogger(__name__)

ALLOWED_IMAGE_MIME_TYPES = {"image/jpeg", "image/png"}
MAX_IMAGE_BYTES = 5 * 1024 * 1024


def is_safe_booking_url(value: str | None) -> bool:
    if value is None:
        return False

    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def validate_image_upload(content_type: str | None, file_size: int) -> None:
    if content_type not in ALLOWED_IMAGE_MIME_TYPES:
        raise AppError(
            422,
            "RESERVATION_IMPORT_UNSUPPORTED_MEDIA_TYPE",
            "이미지는 JPG 또는 PNG만 업로드할 수 있습니다.",
        )

    if file_size > MAX_IMAGE_BYTES:
        raise AppError(
            422,
            "RESERVATION_IMPORT_FILE_TOO_LARGE",
            "이미지 크기는 5MB 이하여야 합니다.",
        )


def resolve_reservation_analysis_model(model: str | None) -> str:
    model_key = (model or "").strip() or DEFAULT_RESERVATION_ANALYSIS_MODEL
    model_name = RESERVATION_ANALYSIS_MODEL_NAMES.get(model_key)
    if not model_name:
        raise AppError(
            422,
            "RESERVATION_IMPORT_INVALID_MODEL",
            "지원하지 않는 분석 모델입니다.",
        )
    return model_name


def _get_reservation_json_text(*, image_bytes: bytes, content_type: str, model_name: str) -> str:
    return get_gemini_reservation_json(
        image_bytes=image_bytes,
        content_type=content_type,
        model_name=model_name,
    )


def _strip_markdown_code_fence(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if len(lines) >= 2 and lines[-1].strip() == "```":
            cleaned = "\n".join(lines[1:-1]).strip()
        elif len(lines) >= 1:
            cleaned = "\n".join(lines[1:]).strip()
    return cleaned


def analyze_reservation_image_draft(
    image_bytes: bytes,
    content_type: str,
    booking_url: str | None = None,
    model: str | None = None,
) -> ReservationImportAnalyzeOut:
    validate_image_upload(content_type=content_type, file_size=len(image_bytes))

    if booking_url is not None and booking_url.strip() and not is_safe_booking_url(booking_url.strip()):
        raise AppError(422, "RESERVATION_IMPORT_INVALID_BOOKING_URL", "예약 링크 형식이 올바르지 않습니다.")

    model_name = resolve_reservation_analysis_model(model)
    response_text = _get_reservation_json_text(
        image_bytes=image_bytes,
        content_type=content_type,
        model_name=model_name,
    )
    cleaned_json_text = _strip_markdown_code_fence(response_text)

    try:
        raw_payload = json.loads(cleaned_json_text)
    except json.JSONDecodeError as exc:
        logger.warning("reservation import json decode failed: %s", exc.msg)
        raise AppError(
            502,
            "RESERVATION_IMPORT_INVALID_RESPONSE",
            "예약 이미지 분석 결과를 해석할 수 없습니다.",
        ) from exc

    if not isinstance(raw_payload, dict):
        logger.warning("reservation import payload is not a json object")
        raise AppError(
            502,
            "RESERVATION_IMPORT_INVALID_RESPONSE",
            "예약 이미지 분석 결과를 해석할 수 없습니다.",
        )

    # Check if any datetime was timezone-naive in raw payload
    had_timezone_naive_dt = False
    for dt_field in ("departure_at", "arrival_at", "checkin_at", "checkout_at"):
        raw_val = raw_payload.get(dt_field)
        if isinstance(raw_val, str) and raw_val.strip():
            try:
                parsed_dt = datetime.fromisoformat(raw_val.strip())
                if parsed_dt.tzinfo is None or parsed_dt.utcoffset() is None:
                    had_timezone_naive_dt = True
                    break
            except ValueError:
                pass

    try:
        payload = ReservationImportAnalyzeOut.model_validate(raw_payload)
    except Exception as exc:
        if hasattr(exc, "errors"):
            safe_errors = [
                f"{'.'.join(str(p) for p in err.get('loc', []))} - {err.get('type')}"
                for err in exc.errors()
            ]
            logger.warning("reservation import validation failed: %s", ", ".join(safe_errors))
        else:
            logger.warning("reservation import validation failed: %s", type(exc).__name__)
        raise AppError(
            502,
            "RESERVATION_IMPORT_INVALID_RESPONSE",
            "예약 이미지 분석 결과를 해석할 수 없습니다.",
        ) from exc

    requested_booking_url = (booking_url or "").strip() or None
    if requested_booking_url and is_safe_booking_url(requested_booking_url):
        payload.booking_url = requested_booking_url
    elif payload.booking_url and not is_safe_booking_url(payload.booking_url):
        payload.booking_url = None

    if not payload.warnings:
        payload.warnings = [DEFAULT_WARNING]
    elif DEFAULT_WARNING not in payload.warnings:
        payload.warnings.append(DEFAULT_WARNING)

    if had_timezone_naive_dt and TIMEZONE_FALLBACK_WARNING not in payload.warnings:
        payload.warnings.append(TIMEZONE_FALLBACK_WARNING)

    return payload
