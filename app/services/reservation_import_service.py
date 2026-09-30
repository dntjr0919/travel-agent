from __future__ import annotations

import json
import logging
from datetime import datetime
from urllib.parse import urlparse

from app.core.config import get_settings
from app.core.errors import AppError
from app.schemas.reservation_import import DEFAULT_WARNING, TIMEZONE_FALLBACK_WARNING, ReservationImportAnalyzeOut

logger = logging.getLogger(__name__)

ALLOWED_IMAGE_MIME_TYPES = {"image/jpeg", "image/png"}
MAX_IMAGE_BYTES = 5 * 1024 * 1024
GEMINI_MODEL_NAME = "gemini-3.5-flash-lite"


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


def _get_gemini_json_text(image_bytes: bytes, content_type: str) -> str:
    settings = get_settings()

    if not settings.gemini_api_key:
        raise AppError(
            503,
            "RESERVATION_IMPORT_NOT_CONFIGURED",
            "API 키를 등록해주세요.",
        )

    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        raise AppError(
            503,
            "RESERVATION_IMPORT_SDK_UNAVAILABLE",
            "예약 이미지 분석 SDK를 사용할 수 없습니다.",
        ) from exc

    prompt = """
이미지에 포함된 예약 정보를 JSON으로만 반환하세요.
- kind: transport 또는 accommodation
- transport_mode: flight, train, intercity_bus 중 하나 또는 null
- title: 예약 항목 제목 (예: [항공] 대한항공 KE703, [숙소] 호텔명)
- provider_name, service_number, departure_name, arrival_name, accommodation_name, currency, memo: 문자열 또는 null
- departure_at, arrival_at, checkin_at, checkout_at: ISO8601 형식(예: 2026-10-10T09:00:00+09:00 또는 2026-10-10T09:00:00) 또는 null
- price_amount: 쉼표나 통화 기호 없는 순수 숫자(예: 285000) 또는 null
- booking_url: null
- warnings: 원본 대조 안내를 포함한 문자열 배열
- 확실하지 않은 값은 추측하지 말고 null
- 예약번호, QR/바코드, 여권, 카드번호, 이름, 연락처는 무시하고 반환하지 말 것
반드시 마크다운이나 추가 설명 없이 순수 JSON 객체 하나만 출력하세요.
""".strip()

    client = genai.Client(api_key=settings.gemini_api_key)

    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL_NAME,
            contents=[
                prompt,
                types.Part.from_bytes(data=image_bytes, mime_type=content_type),
            ],
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
    except Exception as exc:
        raise AppError(
            502,
            "RESERVATION_IMPORT_PROVIDER_ERROR",
            "예약 이미지 분석 중 외부 서비스 호출에 실패했습니다.",
        ) from exc

    response_text = getattr(response, "text", None)
    if not response_text or not response_text.strip():
        raise AppError(
            502,
            "RESERVATION_IMPORT_INVALID_RESPONSE",
            "예약 이미지 분석 결과를 해석할 수 없습니다.",
        )

    return response_text

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
) -> ReservationImportAnalyzeOut:
    validate_image_upload(content_type=content_type, file_size=len(image_bytes))

    if booking_url is not None and booking_url.strip() and not is_safe_booking_url(booking_url.strip()):
        raise AppError(422, "RESERVATION_IMPORT_INVALID_BOOKING_URL", "예약 링크 형식이 올바르지 않습니다.")

    response_text = _get_gemini_json_text(image_bytes=image_bytes, content_type=content_type)
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
