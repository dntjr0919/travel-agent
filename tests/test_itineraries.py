from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import register_and_login
from tests.test_invitations import extract_token, invite_member
from tests.test_trips import create_trip


def create_itinerary(client: TestClient, trip_id: int, **overrides) -> dict:
    payload = {
        "title": "Airport Pickup",
        "category": "transportation",
        "start_at": "2026-11-01T09:00:00+09:00",
        "end_at": "2026-11-01T10:00:00+09:00",
        "location_name": "Jeju Airport",
        "memo": "welcome",
    }
    payload.update(overrides)
    res = client.post(f"/api/trips/{trip_id}/itineraries", json=payload)
    assert res.status_code == 201
    return res.json()


def test_create_itinerary_with_location_metadata_success(client):
    register_and_login(client, "owner-location-create@example.com")
    trip = create_trip(client)

    payload = {
        "title": "맛집 방문",
        "category": "food",
        "start_at": "2026-11-01T12:00:00+09:00",
        "end_at": "2026-11-01T13:00:00+09:00",
        "location_name": "제주 맛집",
        "place_candidate_id": 12,
        "place_provider": "google",
        "external_place_id": "google-place-123",
        "latitude": 33.4996,
        "longitude": 126.5312,
    }

    res = client.post(f"/api/trips/{trip['id']}/itineraries", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert data["place_candidate_id"] == 12
    assert data["place_provider"] == "google"
    assert data["external_place_id"] == "google-place-123"
    assert data["latitude"] == 33.4996
    assert data["longitude"] == 126.5312


def test_create_itinerary_rejects_only_latitude(client):
    register_and_login(client, "owner-location-lat-only@example.com")
    trip = create_trip(client)

    res = client.post(
        f"/api/trips/{trip['id']}/itineraries",
        json={
            "title": "위도만 있음",
            "category": "other",
            "latitude": 33.4,
        },
    )

    assert res.status_code == 422


def test_create_itinerary_rejects_only_longitude(client):
    register_and_login(client, "owner-location-lng-only@example.com")
    trip = create_trip(client)

    res = client.post(
        f"/api/trips/{trip['id']}/itineraries",
        json={
            "title": "경도만 있음",
            "category": "other",
            "longitude": 126.5,
        },
    )

    assert res.status_code == 422


def test_create_itinerary_rejects_latitude_out_of_range(client):
    register_and_login(client, "owner-location-lat-range@example.com")
    trip = create_trip(client)

    res = client.post(
        f"/api/trips/{trip['id']}/itineraries",
        json={
            "title": "범위 초과 위도",
            "category": "other",
            "latitude": 95,
            "longitude": 126.5,
        },
    )

    assert res.status_code == 422


def test_create_itinerary_rejects_longitude_out_of_range(client):
    register_and_login(client, "owner-location-lng-range@example.com")
    trip = create_trip(client)

    res = client.post(
        f"/api/trips/{trip['id']}/itineraries",
        json={
            "title": "범위 초과 경도",
            "category": "other",
            "latitude": 33.5,
            "longitude": 181,
        },
    )

    assert res.status_code == 422


def test_create_itinerary_without_location_metadata_still_works(client):
    register_and_login(client, "owner-location-none@example.com")
    trip = create_trip(client)

    item = create_itinerary(client, trip["id"])

    assert item["place_candidate_id"] is None
    assert item["place_provider"] is None
    assert item["external_place_id"] is None
    assert item["latitude"] is None
    assert item["longitude"] is None


def test_existing_itinerary_list_works_without_location_metadata(client):
    register_and_login(client, "owner-location-list@example.com")
    trip = create_trip(client)
    create_itinerary(client, trip["id"])

    res = client.get(f"/api/trips/{trip['id']}/itineraries")

    assert res.status_code == 200
    items = res.json()
    assert len(items) == 1
    assert items[0]["latitude"] is None
    assert items[0]["longitude"] is None


def test_update_itinerary_location_metadata_updates_and_keeps_version_policy(client):
    register_and_login(client, "owner-location-update@example.com")
    trip = create_trip(client)
    created = create_itinerary(
        client,
        trip["id"],
        place_candidate_id=1,
        place_provider="google",
        external_place_id="p1",
        latitude=33.1,
        longitude=126.1,
    )

    update_res = client.patch(
        f"/api/itineraries/{created['id']}",
        json={
            "version": created["version"],
            "place_provider": "kakao",
            "external_place_id": "kakao-place-9",
            "latitude": 33.2,
            "longitude": 126.2,
        },
    )
    assert update_res.status_code == 200
    updated = update_res.json()
    assert updated["place_candidate_id"] == 1
    assert updated["place_provider"] == "kakao"
    assert updated["external_place_id"] == "kakao-place-9"
    assert updated["latitude"] == 33.2
    assert updated["longitude"] == 126.2

    stale_res = client.patch(
        f"/api/itineraries/{created['id']}",
        json={
            "version": created["version"],
            "title": "stale update",
        },
    )
    assert stale_res.status_code == 409
    assert stale_res.json()["code"] == "ITINERARY_VERSION_CONFLICT"


def test_transport_draft_payload_can_create_itinerary(client):
    register_and_login(client, "owner-transport@example.com")
    trip = create_trip(client)

    payload = {
        "title": "[교통] 서울역 -> 부산역",
        "category": "transportation",
        "status": "planned",
        "start_at": "2026-11-02T08:00:00+09:00",
        "end_at": "2026-11-02T10:30:00+09:00",
        "location_name": "서울역 -> 부산역",
        "memo": "예약 링크: https://www.letskorail.com/example\n예약처: 코레일\n가격: 59800 KRW\n교통수단: 기차",
    }

    res = client.post(f"/api/trips/{trip['id']}/itineraries", json=payload)
    assert res.status_code == 201

    created = res.json()
    assert created["category"] == "transportation"
    assert created["status"] == "planned"
    assert created["location_name"] == "서울역 -> 부산역"
    assert "예약 링크:" in created["memo"]
    assert "교통수단:" in created["memo"]


def test_accommodation_draft_payload_can_create_itinerary(client):
    register_and_login(client, "owner-accommodation@example.com")
    trip = create_trip(client)

    payload = {
        "title": "[숙소] 해운대 호텔 체크인",
        "category": "accommodation",
        "status": "planned",
        "start_at": "2026-11-03T15:00:00+09:00",
        "end_at": "2026-11-03T16:00:00+09:00",
        "location_name": "해운대 호텔",
        "memo": "예약 링크: https://www.agoda.com/example\n예약처: Agoda\n체크아웃 시각: 2026-11-04 11:00",
    }

    res = client.post(f"/api/trips/{trip['id']}/itineraries", json=payload)
    assert res.status_code == 201

    created = res.json()
    assert created["category"] == "accommodation"
    assert created["status"] == "planned"
    assert created["location_name"] == "해운대 호텔"
    assert "체크아웃 시각:" in created["memo"]


def test_end_before_start_is_rejected(client):
    register_and_login(client, "owner@example.com")
    trip = create_trip(client)
    res = client.post(
        f"/api/trips/{trip['id']}/itineraries",
        json={
            "title": "Bad Item",
            "category": "other",
            "start_at": "2026-11-01T10:00:00+09:00",
            "end_at": "2026-11-01T09:00:00+09:00",
        },
    )
    assert res.status_code == 422
    assert res.json()["code"] == "INVALID_TIME_RANGE"


def test_version_conflict_on_concurrent_update(client):
    register_and_login(client, "owner2@example.com")
    trip = create_trip(client)
    item = create_itinerary(client, trip["id"])

    first_update = client.patch(
        f"/api/itineraries/{item['id']}",
        json={"title": "Updated by first", "version": item["version"]},
    )
    assert first_update.status_code == 200
    assert first_update.json()["version"] == 2

    second_update = client.patch(
        f"/api/itineraries/{item['id']}",
        json={"title": "Updated by second (stale)", "version": item["version"]},
    )
    assert second_update.status_code == 409
    assert second_update.json()["code"] == "ITINERARY_VERSION_CONFLICT"


def test_editor_can_create_update_delete_itinerary(client):
    register_and_login(client, "owner3@example.com")
    trip = create_trip(client)
    invitation = invite_member(client, trip["id"], "editor@example.com", "editor")
    token = extract_token(invitation["invite_url"])
    client.post("/api/auth/logout")

    register_and_login(client, "editor@example.com")
    client.post(f"/api/invitations/{token}/accept")

    item = create_itinerary(client, trip["id"])
    update_res = client.patch(
        f"/api/itineraries/{item['id']}", json={"title": "Changed", "version": item["version"]}
    )
    assert update_res.status_code == 200

    delete_res = client.delete(f"/api/itineraries/{item['id']}")
    assert delete_res.status_code == 204


def test_viewer_cannot_mutate_itinerary(client):
    register_and_login(client, "owner4@example.com")
    trip = create_trip(client)
    item = create_itinerary(client, trip["id"])

    invitation = invite_member(client, trip["id"], "viewer@example.com", "viewer")
    token = extract_token(invitation["invite_url"])
    client.post("/api/auth/logout")

    register_and_login(client, "viewer@example.com")
    client.post(f"/api/invitations/{token}/accept")

    create_res = client.post(f"/api/trips/{trip['id']}/itineraries", json={"title": "Nope", "category": "other"})
    assert create_res.status_code == 403
    assert create_res.json()["code"] == "FORBIDDEN"

    update_res = client.patch(f"/api/itineraries/{item['id']}", json={"title": "Nope", "version": item["version"]})
    assert update_res.status_code == 403

    delete_res = client.delete(f"/api/itineraries/{item['id']}")
    assert delete_res.status_code == 403
