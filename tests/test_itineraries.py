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
