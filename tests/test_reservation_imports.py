from __future__ import annotations

import json

from app.core.config import get_settings
from tests.conftest import register_and_login
from tests.test_invitations import extract_token, invite_member
from tests.test_trips import create_trip


def test_analyze_reservation_image_transport_success(client, monkeypatch):
    register_and_login(client, "owner-image-transport@example.com")
    trip = create_trip(client)

    def fake_gemini_json_text(*, image_bytes: bytes, content_type: str, model_name: str) -> str:
        assert content_type == "image/png"
        assert image_bytes
        assert model_name == "gemini-3.5-flash-lite"
        return json.dumps(
            {
                "kind": "transport",
                "transport_mode": "flight",
                "title": "[항공] 대한항공 KE703",
                "provider_name": "대한항공",
                "service_number": "KE703",
                "departure_name": "인천국제공항",
                "arrival_name": "나리타국제공항",
                "departure_at": "2026-10-10T09:00:00+09:00",
                "arrival_at": "2026-10-10T11:20:00+09:00",
                "accommodation_name": None,
                "checkin_at": None,
                "checkout_at": None,
                "price_amount": 285000,
                "currency": "KRW",
                "booking_url": None,
                "memo": "위탁수하물 15kg 포함",
                "warnings": ["AI가 추출한 초안입니다. 원본 예약 정보와 대조한 뒤 저장하세요."],
            }
        )

    monkeypatch.setattr(
        "app.services.reservation_import_service._get_reservation_json_text",
        fake_gemini_json_text,
    )

    res = client.post(
        f"/api/trips/{trip['id']}/reservation-imports/analyze-image",
        data={"booking_url": "https://example.com/reservation"},
        files={"file": ("reservation.png", b"\x89PNG\r\n\x1a\n123", "image/png")},
    )

    assert res.status_code == 200
    data = res.json()

    assert data["kind"] == "transport"
    assert data["transport_mode"] == "flight"
    assert data["provider_name"] == "대한항공"
    assert data["booking_url"] == "https://example.com/reservation"
    assert data["warnings"]


def test_analyze_reservation_image_accommodation_success(client, monkeypatch):
    register_and_login(client, "owner-image-accommodation@example.com")
    trip = create_trip(client)

    def fake_gemini_json_text(*, image_bytes: bytes, content_type: str, model_name: str) -> str:
        assert content_type == "image/jpeg"
        assert image_bytes
        assert model_name == "gemini-3.5-flash-lite"
        return json.dumps(
            {
                "kind": "accommodation",
                "transport_mode": None,
                "title": "[숙소] Hotel Example",
                "provider_name": "Agoda",
                "service_number": None,
                "departure_name": None,
                "arrival_name": None,
                "departure_at": None,
                "arrival_at": None,
                "accommodation_name": "Hotel Example",
                "checkin_at": "2026-10-10T15:00:00+09:00",
                "checkout_at": "2026-10-13T11:00:00+09:00",
                "price_amount": 420000,
                "currency": "KRW",
                "booking_url": None,
                "memo": "조식 포함",
                "warnings": ["AI가 추출한 초안입니다. 원본 예약 정보와 대조한 뒤 저장하세요."],
            }
        )

    monkeypatch.setattr(
        "app.services.reservation_import_service._get_reservation_json_text",
        fake_gemini_json_text,
    )

    res = client.post(
        f"/api/trips/{trip['id']}/reservation-imports/analyze-image",
        files={"file": ("reservation.jpg", b"\xff\xd8\xff\xdb123", "image/jpeg")},
    )

    assert res.status_code == 200
    data = res.json()

    assert data["kind"] == "accommodation"
    assert data["accommodation_name"] == "Hotel Example"
    assert data["checkin_at"] is not None
    assert data["checkout_at"] is not None


def test_viewer_cannot_analyze_reservation_image(client):
    register_and_login(client, "owner-image-viewer@example.com")
    trip = create_trip(client)

    invitation = invite_member(client, trip["id"], "viewer-image@example.com", "viewer")
    token = extract_token(invitation["invite_url"])
    client.post("/api/auth/logout")

    register_and_login(client, "viewer-image@example.com")
    client.post(f"/api/invitations/{token}/accept")

    res = client.post(
        f"/api/trips/{trip['id']}/reservation-imports/analyze-image",
        files={"file": ("reservation.png", b"\x89PNG\r\n\x1a\n123", "image/png")},
    )

    assert res.status_code == 403
    assert res.json()["code"] == "FORBIDDEN"


def test_editor_can_analyze_reservation_image(client, monkeypatch):
    register_and_login(client, "owner-image-editor-test@example.com")
    trip = create_trip(client)

    invitation = invite_member(client, trip["id"], "editor-image@example.com", "editor")
    token = extract_token(invitation["invite_url"])
    client.post("/api/auth/logout")

    register_and_login(client, "editor-image@example.com")
    client.post(f"/api/invitations/{token}/accept")

    def fake_gemini_json_text(*, image_bytes: bytes, content_type: str, model_name: str) -> str:
        assert model_name == "gemini-3.5-flash-lite"
        return json.dumps(
            {
                "kind": "transport",
                "transport_mode": "flight",
                "title": "[항공] 대한항공 KE703",
                "provider_name": "대한항공",
                "service_number": "KE703",
                "departure_name": "인천국제공항",
                "arrival_name": "나리타국제공항",
                "departure_at": "2026-10-10T09:00:00+09:00",
                "arrival_at": "2026-10-10T11:20:00+09:00",
                "accommodation_name": None,
                "checkin_at": None,
                "checkout_at": None,
                "price_amount": 285000,
                "currency": "KRW",
                "booking_url": None,
                "memo": "위탁수하물 15kg 포함",
                "warnings": ["AI가 추출한 초안입니다. 원본 예약 정보와 대조한 뒤 저장하세요."],
            }
        )

    monkeypatch.setattr(
        "app.services.reservation_import_service._get_reservation_json_text",
        fake_gemini_json_text,
    )

    res = client.post(
        f"/api/trips/{trip['id']}/reservation-imports/analyze-image",
        files={"file": ("reservation.png", b"\x89PNG\r\n\x1a\n123", "image/png")},
    )

    assert res.status_code == 200
    assert res.json()["kind"] == "transport"


def test_analyze_reservation_image_rejects_invalid_mime_type(client):
    register_and_login(client, "owner-image-mime@example.com")
    trip = create_trip(client)

    res = client.post(
        f"/api/trips/{trip['id']}/reservation-imports/analyze-image",
        files={"file": ("reservation.gif", b"GIF89a123", "image/gif")},
    )

    assert res.status_code == 422
    assert res.json()["code"] == "RESERVATION_IMPORT_UNSUPPORTED_MEDIA_TYPE"


def test_analyze_reservation_image_rejects_oversized_file(client):
    register_and_login(client, "owner-image-size@example.com")
    trip = create_trip(client)

    oversized_bytes = b"a" * (5 * 1024 * 1024 + 1)

    res = client.post(
        f"/api/trips/{trip['id']}/reservation-imports/analyze-image",
        files={"file": ("reservation.png", oversized_bytes, "image/png")},
    )

    assert res.status_code == 422
    assert res.json()["code"] == "RESERVATION_IMPORT_FILE_TOO_LARGE"


def test_analyze_reservation_image_requires_gemini_api_key(client):
    register_and_login(client, "owner-image-config@example.com")
    trip = create_trip(client)

    settings = get_settings()
    original_api_key = settings.gemini_api_key

    try:
        settings.gemini_api_key = ""

        res = client.post(
            f"/api/trips/{trip['id']}/reservation-imports/analyze-image",
            files={"file": ("reservation.png", b"\x89PNG\r\n\x1a\n123", "image/png")},
        )
    finally:
        settings.gemini_api_key = original_api_key

    assert res.status_code == 503
    assert res.json()["code"] == "RESERVATION_IMPORT_NOT_CONFIGURED"


def test_analyze_reservation_image_timezone_naive_adjusted_to_seoul(client, monkeypatch):
    register_and_login(client, "owner-image-tz-naive@example.com")
    trip = create_trip(client)

    def fake_gemini_json_text(*, image_bytes: bytes, content_type: str, model_name: str) -> str:
        return json.dumps(
            {
                "kind": "transportation",
                "transport_mode": "flight",
                "title": "[항공] 제주항공 7C101",
                "departure_at": "2026-10-10T09:00:00",
                "arrival_at": "2026-10-10T10:15:00",
            }
        )

    monkeypatch.setattr(
        "app.services.reservation_import_service._get_reservation_json_text",
        fake_gemini_json_text,
    )

    res = client.post(
        f"/api/trips/{trip['id']}/reservation-imports/analyze-image",
        files={"file": ("reservation.png", b"\x89PNG\r\n\x1a\n123", "image/png")},
    )

    assert res.status_code == 200
    data = res.json()
    assert data["kind"] == "transport"
    assert data["departure_at"].endswith("+09:00")
    assert data["arrival_at"].endswith("+09:00")
    assert any("Asia/Seoul" in w for w in data["warnings"])


def test_analyze_reservation_image_accommodation_naive_and_normalization(client, monkeypatch):
    register_and_login(client, "owner-image-acc-naive@example.com")
    trip = create_trip(client)

    def fake_gemini_json_text(*, image_bytes: bytes, content_type: str, model_name: str) -> str:
        return json.dumps(
            {
                "kind": "hotel",
                "title": "[숙소] 서울호텔",
                "accommodation_name": "서울호텔",
                "checkin_at": "2026-10-10T15:00:00",
                "checkout_at": "2026-10-11T11:00:00",
            }
        )

    monkeypatch.setattr(
        "app.services.reservation_import_service._get_reservation_json_text",
        fake_gemini_json_text,
    )

    res = client.post(
        f"/api/trips/{trip['id']}/reservation-imports/analyze-image",
        files={"file": ("reservation.png", b"\x89PNG\r\n\x1a\n123", "image/png")},
    )

    assert res.status_code == 200
    data = res.json()
    assert data["kind"] == "accommodation"
    assert data["checkin_at"].endswith("+09:00")
    assert data["checkout_at"].endswith("+09:00")
    assert any("Asia/Seoul" in w for w in data["warnings"])


def test_analyze_reservation_image_preserves_existing_timezone(client, monkeypatch):
    register_and_login(client, "owner-image-tz-aware@example.com")
    trip = create_trip(client)

    def fake_gemini_json_text(*, image_bytes: bytes, content_type: str, model_name: str) -> str:
        return json.dumps(
            {
                "kind": "transport",
                "transport_mode": "rail",
                "title": "[기차] KTX 001",
                "departure_at": "2026-10-10T09:00:00+00:00",
                "arrival_at": "2026-10-10T11:45:00+00:00",
            }
        )

    monkeypatch.setattr(
        "app.services.reservation_import_service._get_reservation_json_text",
        fake_gemini_json_text,
    )

    res = client.post(
        f"/api/trips/{trip['id']}/reservation-imports/analyze-image",
        files={"file": ("reservation.png", b"\x89PNG\r\n\x1a\n123", "image/png")},
    )

    assert res.status_code == 200
    data = res.json()
    assert data["transport_mode"] == "train"
    assert data["departure_at"].endswith("+00:00") or data["departure_at"].endswith("Z")
    assert not any("Asia/Seoul" in w for w in data["warnings"])


def test_analyze_reservation_image_strips_markdown_code_fence(client, monkeypatch):
    register_and_login(client, "owner-image-fence@example.com")
    trip = create_trip(client)

    def fake_gemini_json_text(*, image_bytes: bytes, content_type: str, model_name: str) -> str:
        payload = {
            "kind": "transport",
            "transport_mode": "bus",
            "title": "[고속버스] 서울-부산",
            "departure_at": "2026-10-10T09:00:00+09:00",
        }
        return f"```json\n{json.dumps(payload)}\n```"

    monkeypatch.setattr(
        "app.services.reservation_import_service._get_reservation_json_text",
        fake_gemini_json_text,
    )

    res = client.post(
        f"/api/trips/{trip['id']}/reservation-imports/analyze-image",
        files={"file": ("reservation.png", b"\x89PNG\r\n\x1a\n123", "image/png")},
    )

    assert res.status_code == 200
    data = res.json()
    assert data["kind"] == "transport"
    assert data["transport_mode"] == "intercity_bus"


def test_analyze_reservation_image_invalid_datetime_returns_502(client, monkeypatch):
    register_and_login(client, "owner-image-invalid-dt@example.com")
    trip = create_trip(client)

    def fake_gemini_json_text(*, image_bytes: bytes, content_type: str, model_name: str) -> str:
        return json.dumps(
            {
                "kind": "transport",
                "title": "Invalid Datetime",
                "departure_at": "not-a-datetime",
            }
        )

    monkeypatch.setattr(
        "app.services.reservation_import_service._get_reservation_json_text",
        fake_gemini_json_text,
    )

    res = client.post(
        f"/api/trips/{trip['id']}/reservation-imports/analyze-image",
        files={"file": ("reservation.png", b"\x89PNG\r\n\x1a\n123", "image/png")},
    )

    assert res.status_code == 502
    assert res.json()["code"] == "RESERVATION_IMPORT_INVALID_RESPONSE"


def test_analyze_reservation_image_uses_selected_model(client, monkeypatch):
    register_and_login(client, "owner-image-model-selected@example.com")
    trip = create_trip(client)

    def fake_gemini_json_text(*, image_bytes: bytes, content_type: str, model_name: str) -> str:
        assert model_name == "gemini-3.8-flash"
        return json.dumps(
            {
                "kind": "transport",
                "transport_mode": "flight",
                "title": "[항공] 테스트 항공",
            }
        )

    monkeypatch.setattr(
        "app.services.reservation_import_service._get_reservation_json_text",
        fake_gemini_json_text,
    )

    res = client.post(
        f"/api/trips/{trip['id']}/reservation-imports/analyze-image",
        data={"model": "gemini_flash"},
        files={"file": ("reservation.png", b"\x89PNG\r\n\x1a\n123", "image/png")},
    )

    assert res.status_code == 200
    assert res.json()["kind"] == "transport"


def test_analyze_reservation_image_uses_default_model_when_missing(client, monkeypatch):
    register_and_login(client, "owner-image-model-default-missing@example.com")
    trip = create_trip(client)

    def fake_gemini_json_text(*, image_bytes: bytes, content_type: str, model_name: str) -> str:
        assert model_name == "gemini-3.5-flash-lite"
        return json.dumps(
            {
                "kind": "transport",
                "transport_mode": "flight",
                "title": "[항공] 기본 모델",
            }
        )

    monkeypatch.setattr(
        "app.services.reservation_import_service._get_reservation_json_text",
        fake_gemini_json_text,
    )

    res = client.post(
        f"/api/trips/{trip['id']}/reservation-imports/analyze-image",
        files={"file": ("reservation.png", b"\x89PNG\r\n\x1a\n123", "image/png")},
    )

    assert res.status_code == 200
    assert res.json()["kind"] == "transport"


def test_analyze_reservation_image_uses_default_model_when_blank(client, monkeypatch):
    register_and_login(client, "owner-image-model-default-blank@example.com")
    trip = create_trip(client)

    def fake_gemini_json_text(*, image_bytes: bytes, content_type: str, model_name: str) -> str:
        assert model_name == "gemini-3.5-flash-lite"
        return json.dumps(
            {
                "kind": "transport",
                "transport_mode": "flight",
                "title": "[항공] 기본 모델",
            }
        )

    monkeypatch.setattr(
        "app.services.reservation_import_service._get_reservation_json_text",
        fake_gemini_json_text,
    )

    res = client.post(
        f"/api/trips/{trip['id']}/reservation-imports/analyze-image",
        data={"model": "   "},
        files={"file": ("reservation.png", b"\x89PNG\r\n\x1a\n123", "image/png")},
    )

    assert res.status_code == 200
    assert res.json()["kind"] == "transport"


def test_analyze_reservation_image_rejects_invalid_model(client):
    register_and_login(client, "owner-image-model-invalid@example.com")
    trip = create_trip(client)

    res = client.post(
        f"/api/trips/{trip['id']}/reservation-imports/analyze-image",
        data={"model": "not_supported_model"},
        files={"file": ("reservation.png", b"\x89PNG\r\n\x1a\n123", "image/png")},
    )

    assert res.status_code == 422
    assert res.json()["code"] == "RESERVATION_IMPORT_INVALID_MODEL"
    assert res.json()["detail"] == "지원하지 않는 분석 모델입니다."
