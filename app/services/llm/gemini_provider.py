from __future__ import annotations

from app.core.config import get_settings
from app.core.errors import AppError

RESERVATION_ANALYSIS_PROMPT = """
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


def _build_gemini_client(
    *,
    not_configured_code: str,
    not_configured_detail: str,
    sdk_unavailable_code: str,
    sdk_unavailable_detail: str,
):
    settings = get_settings()

    if not settings.gemini_api_key:
        raise AppError(
            503,
            not_configured_code,
            not_configured_detail,
        )

    try:
        from google import genai
    except ImportError as exc:
        raise AppError(
            503,
            sdk_unavailable_code,
            sdk_unavailable_detail,
        ) from exc

    return genai.Client(api_key=settings.gemini_api_key)


def _generate_gemini_json_response(
    *,
    model_name: str,
    contents: list,
    provider_error_code: str,
    provider_error_detail: str,
    invalid_response_code: str,
    invalid_response_detail: str,
    not_configured_code: str,
    not_configured_detail: str,
    sdk_unavailable_code: str,
    sdk_unavailable_detail: str,
) -> str:
    try:
        from google.genai import types
    except ImportError as exc:
        raise AppError(
            503,
            sdk_unavailable_code,
            sdk_unavailable_detail,
        ) from exc

    client = _build_gemini_client(
        not_configured_code=not_configured_code,
        not_configured_detail=not_configured_detail,
        sdk_unavailable_code=sdk_unavailable_code,
        sdk_unavailable_detail=sdk_unavailable_detail,
    )

    try:
        response = client.models.generate_content(
            model=model_name,
            contents=contents,
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
    except Exception as exc:
        raise AppError(
            502,
            provider_error_code,
            provider_error_detail,
        ) from exc

    response_text = getattr(response, "text", None)
    if not response_text or not response_text.strip():
        raise AppError(
            502,
            invalid_response_code,
            invalid_response_detail,
        )

    return response_text


def get_gemini_text_json(
    *,
    prompt: str,
    model_name: str,
) -> str:
    return _generate_gemini_json_response(
        model_name=model_name,
        contents=[prompt],
        provider_error_code="AI_ITINERARY_PROVIDER_ERROR",
        provider_error_detail="AI 코스 구성 중 외부 서비스 호출에 실패했습니다.",
        invalid_response_code="AI_ITINERARY_INVALID_COURSE_RESPONSE",
        invalid_response_detail="AI 코스 구성 결과를 해석할 수 없습니다.",
        not_configured_code="AI_ITINERARY_PROVIDER_ERROR",
        not_configured_detail="AI 코스 생성을 위한 Gemini API 키가 설정되지 않았습니다.",
        sdk_unavailable_code="AI_ITINERARY_PROVIDER_ERROR",
        sdk_unavailable_detail="AI 코스 생성을 위한 Gemini SDK를 사용할 수 없습니다.",
    )


def get_gemini_reservation_json(
    *,
    image_bytes: bytes,
    content_type: str,
    model_name: str,
) -> str:
    try:
        from google.genai import types
    except ImportError as exc:
        raise AppError(
            503,
            "RESERVATION_IMPORT_SDK_UNAVAILABLE",
            "예약 이미지 분석 SDK를 사용할 수 없습니다.",
        ) from exc

    return _generate_gemini_json_response(
        model_name=model_name,
        contents=[
            RESERVATION_ANALYSIS_PROMPT,
            types.Part.from_bytes(data=image_bytes, mime_type=content_type),
        ],
        provider_error_code="RESERVATION_IMPORT_PROVIDER_ERROR",
        provider_error_detail="예약 이미지 분석 중 외부 서비스 호출에 실패했습니다.",
        invalid_response_code="RESERVATION_IMPORT_INVALID_RESPONSE",
        invalid_response_detail="예약 이미지 분석 결과를 해석할 수 없습니다.",
        not_configured_code="RESERVATION_IMPORT_NOT_CONFIGURED",
        not_configured_detail="API 키를 등록해주세요.",
        sdk_unavailable_code="RESERVATION_IMPORT_SDK_UNAVAILABLE",
        sdk_unavailable_detail="예약 이미지 분석 SDK를 사용할 수 없습니다.",
    )
