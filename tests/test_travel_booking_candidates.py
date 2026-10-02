from __future__ import annotations

import pytest

from tests.conftest import login, register_and_login
from tests.test_invitations import extract_token, invite_member
from tests.test_trips import create_trip


def _setup_member(client, role: str, email: str):
    register_and_login(client, f"owner-{email}")
    trip = create_trip(client)
    invitation = invite_member(client, trip["id"], email, role)
    token = extract_token(invitation["invite_url"])
    client.post("/api/auth/logout")
    register_and_login(client, email)
    client.post(f"/api/invitations/{token}/accept")
    return trip


def _transport_payload(**overrides) -> dict:
    return {
        "kind": "transport",
        "title": "서울에서 부산",
        "transport_mode": "train",
        "provider_name": "JR",
        "service_number": "KTX 101",
        "departure_name": "서울역",
        "arrival_name": "부산역",
        "departure_at": "2026-11-01T09:00:00+09:00",
        "arrival_at": "2026-11-01T11:30:00+09:00",
        "price_amount": 59800,
        "currency": " KRW ",
        "booking_url": "https://example.com/ticket",
        "memo": "창가 좌석",
        **overrides,
    }


def _accommodation_payload(**overrides) -> dict:
    return {
        "kind": "accommodation",
        "title": "오사카 숙소",
        "accommodation_name": "난바 호텔",
        "provider_name": "Booking.com",
        "check_in_at": "2026-11-01T15:00:00+09:00",
        "check_out_at": "2026-11-03T11:00:00+09:00",
        "price_amount": 240000,
        "currency": "KRW",
        "booking_url": "https://example.com/hotel",
        "memo": "조식 포함",
        **overrides,
    }


def test_owner_can_create_transport_and_list_serialized_candidate(client):
    register_and_login(client, "booking-owner@example.com", display_name="Owner")
    trip = create_trip(client)

    created = client.post(
        f"/api/trips/{trip['id']}/booking-candidates",
        json=_transport_payload(),
    )
    assert created.status_code == 201
    candidate = created.json()
    assert candidate["title"] == "서울에서 부산"
    assert candidate["currency"] == "KRW"
    assert candidate["created_by_name"] == "Owner"
    assert candidate["departure_name"] == "서울역"
    assert candidate["created_by"] is not None

    listed = client.get(f"/api/trips/{trip['id']}/booking-candidates")
    assert listed.status_code == 200
    assert listed.json() == [candidate]


def test_candidate_crud_does_not_call_external_services(client, monkeypatch):
    def fail_if_called(*args, **kwargs):
        pytest.fail("candidate storage must not call external services")

    monkeypatch.setattr("app.services.place_search_service.search_places", fail_if_called)
    monkeypatch.setattr("app.services.ai_itinerary_service.get_gemini_text_json", fail_if_called)
    monkeypatch.setattr("app.services.reservation_import_service.analyze_reservation_image_draft", fail_if_called)
    register_and_login(client, "booking-no-external@example.com")
    trip = create_trip(client)

    created = client.post(
        f"/api/trips/{trip['id']}/booking-candidates",
        json=_transport_payload(),
    )
    assert created.status_code == 201
    assert client.get(f"/api/trips/{trip['id']}/booking-candidates").status_code == 200


def test_editor_can_create_accommodation_update_and_delete(client):
    trip = _setup_member(client, "editor", "booking-editor@example.com")
    created = client.post(
        f"/api/trips/{trip['id']}/booking-candidates",
        json=_accommodation_payload(),
    )
    assert created.status_code == 201
    candidate_id = created.json()["id"]
    assert created.json()["accommodation_name"] == "난바 호텔"

    updated = client.patch(
        f"/api/booking-candidates/{candidate_id}",
        json={"memo": "조식 및 취소 조건 확인"},
    )
    assert updated.status_code == 200
    assert updated.json()["memo"] == "조식 및 취소 조건 확인"

    deleted = client.delete(f"/api/booking-candidates/{candidate_id}")
    assert deleted.status_code == 204


def test_update_validates_merged_candidate_and_currency_after_trimming(client):
    register_and_login(client, "booking-update-validation@example.com")
    trip = create_trip(client)
    created = client.post(
        f"/api/trips/{trip['id']}/booking-candidates",
        json=_accommodation_payload(currency=" 123456789012 "),
    )
    assert created.status_code == 201
    candidate_id = created.json()["id"]
    assert created.json()["currency"] == "123456789012"

    invalid_update = client.patch(
        f"/api/booking-candidates/{candidate_id}",
        json={"check_in_at": "2026-11-04T15:00:00+09:00"},
    )
    assert invalid_update.status_code == 422


def test_viewer_can_list_but_cannot_create_update_or_delete(client):
    trip = _setup_member(client, "viewer", "booking-viewer@example.com")
    owner_email = f"owner-booking-viewer@example.com"
    client.post("/api/auth/logout")
    login(client, owner_email)
    created = client.post(
        f"/api/trips/{trip['id']}/booking-candidates",
        json=_transport_payload(),
    )
    assert created.status_code == 201
    candidate_id = created.json()["id"]
    client.post("/api/auth/logout")
    login(client, "booking-viewer@example.com")

    assert client.get(f"/api/trips/{trip['id']}/booking-candidates").status_code == 200
    assert client.post(
        f"/api/trips/{trip['id']}/booking-candidates",
        json=_transport_payload(title="Viewer item"),
    ).status_code == 403
    assert client.patch(
        f"/api/booking-candidates/{candidate_id}", json={"memo": "no"}
    ).status_code == 403
    assert client.delete(f"/api/booking-candidates/{candidate_id}").status_code == 403


def test_other_trip_candidate_mutations_are_forbidden(client):
    register_and_login(client, "unrelated-owner@example.com")
    create_trip(client)
    client.post("/api/auth/logout")

    register_and_login(client, "candidate-owner@example.com")
    other_trip = create_trip(client)
    created = client.post(
        f"/api/trips/{other_trip['id']}/booking-candidates",
        json=_transport_payload(),
    )
    candidate_id = created.json()["id"]
    client.post("/api/auth/logout")

    login(client, "unrelated-owner@example.com")
    assert client.patch(
        f"/api/booking-candidates/{candidate_id}", json={"memo": "no"}
    ).status_code == 403
    assert client.delete(f"/api/booking-candidates/{candidate_id}").status_code == 403


@pytest.mark.parametrize(
    "payload",
    [
        {"kind": "transport", "title": "missing mode"},
        {"kind": "accommodation", "title": "missing accommodation"},
        _transport_payload(
            departure_at="2026-11-01T11:00:00+09:00",
            arrival_at="2026-11-01T10:00:00+09:00",
        ),
        _accommodation_payload(
            check_in_at="2026-11-02T15:00:00+09:00",
            check_out_at="2026-11-01T11:00:00+09:00",
        ),
        _transport_payload(booking_url="ftp://example.com/ticket"),
        _transport_payload(price_amount=-1),
    ],
)
def test_invalid_candidate_payloads_return_422(client, payload):
    register_and_login(client, "booking-validation@example.com")
    trip = create_trip(client)
    response = client.post(
        f"/api/trips/{trip['id']}/booking-candidates",
        json=payload,
    )
    assert response.status_code == 422


def test_candidate_order_uses_kind_then_date_nulls_last(client):
    register_and_login(client, "booking-sort@example.com")
    trip = create_trip(client)
    payloads = [
        _accommodation_payload(title="숙박 날짜 없음", check_in_at=None, check_out_at=None),
        _transport_payload(title="교통 날짜 없음", departure_at=None, arrival_at=None),
        _accommodation_payload(title="숙박 날짜 있음"),
        _transport_payload(title="교통 날짜 있음"),
    ]
    for payload in payloads:
        assert client.post(
            f"/api/trips/{trip['id']}/booking-candidates", json=payload
        ).status_code == 201

    listed = client.get(f"/api/trips/{trip['id']}/booking-candidates")
    assert [item["title"] for item in listed.json()] == [
        "숙박 날짜 있음",
        "숙박 날짜 없음",
        "교통 날짜 있음",
        "교통 날짜 없음",
    ]