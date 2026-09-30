from __future__ import annotations

import json
from urllib.parse import urlparse

from app.core.config import get_settings
from app.core.errors import AppError
from app.schemas.reservation_import import DEFAULT_WARNING, ReservationImportAnalyzeOut

ALLOWED_IMAGE_MIME_TYPES = {"image/jpeg", "image/png"}
MAX_IMAGE_BYTES = 5 * 1024 * 1024
GEMINI_MODEL_NAME = "gemini-2.5-flash"


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
            "예약 이미지 분석 기능이 아직 설정되지 않았습니다.",
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
- transport_mode: flight/train/intercity_bus 또는 null
- title, provider_name, service_number, departure_name, arrival_name,
  departure_at, arrival_at, accommodation_name, checkin_at, checkout_at,
  price_amount, currency, booking_url, memo, warnings 필드만 반환
- 시간은 timezone-aware ISO8601(예: 2026-10-10T09:00:00+09:00) 또는 null
- 확실하지 않은 값은 추측하지 말고 null
- 예약번호, QR/바코드, 여권, 카드번호, 이름, 연락처는 무시하고 반환하지 말 것
- warnings에는 반드시 검토 안내 문구를 포함
JSON 외 텍스트를 절대 출력하지 마세요.
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


def analyze_reservation_image_draft(
    image_bytes: bytes,
    content_type: str,
    booking_url: str | None = None,
) -> ReservationImportAnalyzeOut:
    validate_image_upload(content_type=content_type, file_size=len(image_bytes))

    if booking_url is not None and booking_url.strip() and not is_safe_booking_url(booking_url.strip()):
        raise AppError(422, "RESERVATION_IMPORT_INVALID_BOOKING_URL", "예약 링크 형식이 올바르지 않습니다.")

    response_text = _get_gemini_json_text(image_bytes=image_bytes, content_type=content_type)

    try:
        raw_payload = json.loads(response_text)
    except json.JSONDecodeError as exc:
        raise AppError(
            502,
            "RESERVATION_IMPORT_INVALID_RESPONSE",
            "예약 이미지 분석 결과를 해석할 수 없습니다.",
        ) from exc

    try:
        payload = ReservationImportAnalyzeOut.model_validate(raw_payload)
    except Exception as exc:
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

    return payload
