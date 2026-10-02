from __future__ import annotations

from app.core.config import get_settings
from app.core.errors import AppError
from tests.conftest import register_and_login
from tests.test_invitations import extract_token, invite_member
from tests.test_trips import create_trip


def _owner_trip(client):
    register_and_login(client, "owner-route@example.com")
    return create_trip(client)


def _editor_trip(client):
    register_and_login(client, "owner-route-editor@example.com")
    trip = create_trip(client)
    invitation = invite_member(client, trip["id"], "editor-route@example.com", "editor")
    token = extract_token(invitation["invite_url"])

    client.post("/api/auth/logout")
    register_and_login(client, "editor-route@example.com")
    client.post(f"/api/invitations/{token}/accept")
    return trip


def _viewer_trip(client):
    register_and_login(client, "owner-route-viewer@example.com")
    trip = create_trip(client)
    invitation = invite_member(client, trip["id"], "viewer-route@example.com", "viewer")
    token = extract_token(invitation["invite_url"])

    client.post("/api/auth/logout")
    register_and_login(client, "viewer-route@example.com")
    client.post(f"/api/invitations/{token}/accept")
    return trip


def _valid_payload() -> dict:
    return {
        "days": [
            {
                "date": "2026-11-01",
                "places": [
                    {
                        "external_place_id": "place-a",
                        "latitude": 33.450701,
                        "longitude": 126.570667,
                    },
                    {
                        "external_place_id": "place-b",
                        "latitude": 33.448933,
                        "longitude": 126.571227,
                    },
                ],
            }
        ]
    }


def _set_trip_dates(client, trip_id: int, start_date: str, end_date: str) -> None:
    res = client.patch(
        f"/api/trips/{trip_id}",
        json={
            "start_date": start_date,
            "end_date": end_date,
        },
    )
    assert res.status_code == 200


def _places_for_count(prefix: str, count: int) -> list[dict]:
    places: list[dict] = []
    for index in range(count):
        places.append(
            {
                "external_place_id": f"{prefix}-{index + 1}",
                "latitude": 33.45 + (index * 0.001),
                "longitude": 126.57 + (index * 0.001),
            }
        )
    return places


def test_owner_can_calculate_walking_route(client, monkeypatch):
    trip = _owner_trip(client)

    def fake_compute_walking_leg(**kwargs):
        return 840, 1000

    monkeypatch.setattr(
        "app.services.ai_itinerary_route_service.compute_walking_leg",
        fake_compute_walking_leg,
    )

    res = client.post(
        f"/api/trips/{trip['id']}/ai-itinerary-drafts/routes",
        json=_valid_payload(),
    )

    assert res.status_code == 200
    data = res.json()
    assert data["travel_mode"] == "WALK"
    assert len(data["days"][0]["legs"]) == 1
    assert data["days"][0]["legs"][0]["duration_seconds"] == 840
    assert data["days"][0]["legs"][0]["distance_meters"] == 1000


def test_editor_can_calculate_walking_route(client, monkeypatch):
    trip = _editor_trip(client)

    monkeypatch.setattr(
        "app.services.ai_itinerary_route_service.compute_walking_leg",
        lambda **kwargs: (600, 800),
    )

    res = client.post(
        f"/api/trips/{trip['id']}/ai-itinerary-drafts/routes",
        json=_valid_payload(),
    )

    assert res.status_code == 200


def test_viewer_forbidden(client):
    trip = _viewer_trip(client)

    res = client.post(
        f"/api/trips/{trip['id']}/ai-itinerary-drafts/routes",
        json=_valid_payload(),
    )

    assert res.status_code == 403
    assert res.json()["code"] == "FORBIDDEN"


def test_missing_google_maps_key_returns_503(client):
    trip = _owner_trip(client)

    settings = get_settings()
    original = settings.google_maps_api_key

    try:
        settings.google_maps_api_key = ""
        res = client.post(
            f"/api/trips/{trip['id']}/ai-itinerary-drafts/routes",
            json=_valid_payload(),
        )
    finally:
        settings.google_maps_api_key = original

    assert res.status_code == 503
    assert res.json()["code"] == "AI_ITINERARY_ROUTE_NOT_CONFIGURED"


def test_invalid_date_outside_trip_returns_422(client):
    trip = _owner_trip(client)

    payload = _valid_payload()
    payload["days"][0]["date"] = "2026-12-01"

    res = client.post(
        f"/api/trips/{trip['id']}/ai-itinerary-drafts/routes",
        json=payload,
    )

    assert res.status_code == 422
    assert res.json()["code"] == "AI_ITINERARY_ROUTE_INVALID_DATE"


def test_too_many_places_per_day_or_total_returns_422(client):
    trip = _owner_trip(client)

    payload_too_many_in_day = {
        "days": [
            {
                "date": "2026-11-01",
                "places": [
                    {"external_place_id": "p1", "latitude": 33.1, "longitude": 126.1},
                    {"external_place_id": "p2", "latitude": 33.2, "longitude": 126.2},
                    {"external_place_id": "p3", "latitude": 33.3, "longitude": 126.3},
                    {"external_place_id": "p4", "latitude": 33.4, "longitude": 126.4},
                    {"external_place_id": "p5", "latitude": 33.5, "longitude": 126.5},
                ],
            }
        ]
    }

    res_day = client.post(
        f"/api/trips/{trip['id']}/ai-itinerary-drafts/routes",
        json=payload_too_many_in_day,
    )

    assert res_day.status_code == 422
    assert res_day.json()["code"] == "AI_ITINERARY_ROUTE_TOO_MANY_PLACES"

    payload_too_many_total = {
        "days": [
            {
                "date": "2026-11-01",
                "places": [
                    {"external_place_id": "a1", "latitude": 33.1, "longitude": 126.1},
                    {"external_place_id": "a2", "latitude": 33.2, "longitude": 126.2},
                    {"external_place_id": "a3", "latitude": 33.3, "longitude": 126.3},
                    {"external_place_id": "a4", "latitude": 33.4, "longitude": 126.4},
                ],
            },
            {
                "date": "2026-11-02",
                "places": [
                    {"external_place_id": "b1", "latitude": 33.1, "longitude": 126.1},
                    {"external_place_id": "b2", "latitude": 33.2, "longitude": 126.2},
                    {"external_place_id": "b3", "latitude": 33.3, "longitude": 126.3},
                    {"external_place_id": "b4", "latitude": 33.4, "longitude": 126.4},
                ],
            },
            {
                "date": "2026-11-03",
                "places": [
                    {"external_place_id": "c1", "latitude": 33.1, "longitude": 126.1},
                    {"external_place_id": "c2", "latitude": 33.2, "longitude": 126.2},
                    {"external_place_id": "c3", "latitude": 33.3, "longitude": 126.3},
                    {"external_place_id": "c4", "latitude": 33.4, "longitude": 126.4},
                ],
            },
            {
                "date": "2026-11-04",
                "places": [
                    {"external_place_id": "d1", "latitude": 33.1, "longitude": 126.1},
                    {"external_place_id": "d2", "latitude": 33.2, "longitude": 126.2},
                    {"external_place_id": "d3", "latitude": 33.3, "longitude": 126.3},
                    {"external_place_id": "d4", "latitude": 33.4, "longitude": 126.4},
                ],
            },
            {
                "date": "2026-11-05",
                "places": [
                    {"external_place_id": "e1", "latitude": 33.1, "longitude": 126.1},
                    {"external_place_id": "e2", "latitude": 33.2, "longitude": 126.2},
                    {"external_place_id": "e3", "latitude": 33.3, "longitude": 126.3},
                    {"external_place_id": "e4", "latitude": 33.4, "longitude": 126.4},
                ],
            },
            {
                "date": "2026-11-01",
                "places": [
                    {"external_place_id": "x1", "latitude": 33.9, "longitude": 126.9},
                    {"external_place_id": "x2", "latitude": 33.8, "longitude": 126.8},
                ],
            },
        ]
    }

    res_total = client.post(
        f"/api/trips/{trip['id']}/ai-itinerary-drafts/routes",
        json=payload_too_many_total,
    )

    assert res_total.status_code == 422
    assert res_total.json()["code"] == "AI_ITINERARY_ROUTE_TOO_MANY_PLACES"


def test_provider_error_returns_502(client, monkeypatch):
    trip = _owner_trip(client)

    def fake_compute_walking_leg(**kwargs):
        raise AppError(502, "AI_ITINERARY_ROUTE_PROVIDER_ERROR", "provider failure")

    monkeypatch.setattr(
        "app.services.ai_itinerary_route_service.compute_walking_leg",
        fake_compute_walking_leg,
    )

    res = client.post(
        f"/api/trips/{trip['id']}/ai-itinerary-drafts/routes",
        json=_valid_payload(),
    )

    assert res.status_code == 502
    assert res.json()["code"] == "AI_ITINERARY_ROUTE_PROVIDER_ERROR"


def test_invalid_provider_response_returns_502(client, monkeypatch):
    trip = _owner_trip(client)

    def fake_compute_walking_leg(**kwargs):
        raise AppError(502, "AI_ITINERARY_ROUTE_INVALID_RESPONSE", "invalid response")

    monkeypatch.setattr(
        "app.services.ai_itinerary_route_service.compute_walking_leg",
        fake_compute_walking_leg,
    )

    res = client.post(
        f"/api/trips/{trip['id']}/ai-itinerary-drafts/routes",
        json=_valid_payload(),
    )

    assert res.status_code == 502
    assert res.json()["code"] == "AI_ITINERARY_ROUTE_INVALID_RESPONSE"


def test_duplicate_place_id_returns_422(client):
    trip = _owner_trip(client)

    payload = {
        "days": [
            {
                "date": "2026-11-01",
                "places": [
                    {
                        "external_place_id": "same-id",
                        "latitude": 33.450701,
                        "longitude": 126.570667,
                    },
                    {
                        "external_place_id": "same-id",
                        "latitude": 33.448933,
                        "longitude": 126.571227,
                    },
                ],
            }
        ]
    }

    res = client.post(
        f"/api/trips/{trip['id']}/ai-itinerary-drafts/routes",
        json=payload,
    )

    assert res.status_code == 422


def test_six_day_trip_accepts_up_to_twenty_four_places(client, monkeypatch):
    trip = _owner_trip(client)
    _set_trip_dates(client, trip["id"], "2027-01-17", "2027-01-22")

    monkeypatch.setattr(
        "app.services.ai_itinerary_route_service.compute_walking_leg",
        lambda **kwargs: (600, 800),
    )

    payload = {
        "days": [
            {"date": "2027-01-17", "places": _places_for_count("d1", 4)},
            {"date": "2027-01-18", "places": _places_for_count("d2", 4)},
            {"date": "2027-01-19", "places": _places_for_count("d3", 4)},
            {"date": "2027-01-20", "places": _places_for_count("d4", 4)},
            {"date": "2027-01-21", "places": _places_for_count("d5", 4)},
            {"date": "2027-01-22", "places": _places_for_count("d6", 4)},
        ]
    }

    res = client.post(
        f"/api/trips/{trip['id']}/ai-itinerary-drafts/routes",
        json=payload,
    )

    assert res.status_code == 200
    assert len(res.json()["days"]) == 6


def test_six_day_trip_rejects_twenty_five_places(client):
    trip = _owner_trip(client)
    _set_trip_dates(client, trip["id"], "2027-01-17", "2027-01-22")

    payload = {
        "days": [
            {"date": "2027-01-17", "places": _places_for_count("d1", 4)},
            {"date": "2027-01-18", "places": _places_for_count("d2", 4)},
            {"date": "2027-01-19", "places": _places_for_count("d3", 4)},
            {"date": "2027-01-20", "places": _places_for_count("d4", 4)},
            {"date": "2027-01-21", "places": _places_for_count("d5", 4)},
            {"date": "2027-01-22", "places": _places_for_count("d6", 5)},
        ]
    }

    res = client.post(
        f"/api/trips/{trip['id']}/ai-itinerary-drafts/routes",
        json=payload,
    )

    assert res.status_code == 422
    assert res.json()["code"] == "AI_ITINERARY_ROUTE_TOO_MANY_PLACES"


def test_rejects_when_request_day_count_exceeds_trip_day_count(client):
    trip = _owner_trip(client)

    payload = {
        "days": [
            {"date": "2026-11-01", "places": _places_for_count("d1", 2)},
            {"date": "2026-11-02", "places": _places_for_count("d2", 2)},
            {"date": "2026-11-03", "places": _places_for_count("d3", 2)},
            {"date": "2026-11-04", "places": _places_for_count("d4", 2)},
            {"date": "2026-11-05", "places": _places_for_count("d5", 2)},
            {"date": "2026-11-06", "places": _places_for_count("d6", 2)},
        ]
    }

    res = client.post(
        f"/api/trips/{trip['id']}/ai-itinerary-drafts/routes",
        json=payload,
    )

    assert res.status_code == 422
    assert res.json()["code"] == "AI_ITINERARY_ROUTE_TOO_MANY_PLACES"


def test_duplicate_day_rejected_with_422(client):
    trip = _owner_trip(client)

    payload = {
        "days": [
            {"date": "2026-11-01", "places": _places_for_count("d1", 2)},
            {"date": "2026-11-01", "places": _places_for_count("d2", 2)},
        ]
    }

    res = client.post(
        f"/api/trips/{trip['id']}/ai-itinerary-drafts/routes",
        json=payload,
    )

    assert res.status_code == 422
    assert res.json()["code"] == "AI_ITINERARY_ROUTE_INVALID_DATE"
