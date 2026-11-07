from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import register_and_login


def create_trip(client: TestClient, **overrides) -> dict:
    payload = {
        "title": "Jeju Trip",
        "destination": "Jeju",
        "start_date": "2026-11-01",
        "end_date": "2026-11-05",
        "timezone": "Asia/Seoul",
    }
    payload.update(overrides)
    res = client.post(
        "/api/trips",
        json=payload,
    )
    assert res.status_code == 201
    return res.json()


def test_owner_trip_creates_owner_member(client):
    register_and_login(client, "owner@example.com")
    trip = create_trip(client)
    assert trip["my_role"] == "owner"

    members_res = client.get(f"/api/trips/{trip['id']}/members")
    assert members_res.status_code == 200
    members = members_res.json()
    assert len(members) == 1
    assert members[0]["role"] == "owner"
    assert members[0]["email"] == "owner@example.com"


def test_other_user_cannot_access_private_trip(client):
    register_and_login(client, "owner2@example.com")
    trip = create_trip(client)
    client.post("/api/auth/logout")

    register_and_login(client, "stranger@example.com")
    res = client.get(f"/api/trips/{trip['id']}")
    assert res.status_code == 403
    assert res.json()["code"] == "FORBIDDEN"


def test_invalid_date_range_rejected(client):
    register_and_login(client, "owner3@example.com")
    res = client.post(
        "/api/trips",
        json={
            "title": "Bad Trip",
            "start_date": "2026-11-10",
            "end_date": "2026-11-01",
            "timezone": "Asia/Seoul",
        },
    )
    assert res.status_code == 422
    assert res.json()["code"] == "INVALID_DATE_RANGE"


def test_owner_can_delete_trip_and_others_remain(client):
    register_and_login(client, "owner-delete@example.com")
    first = create_trip(client)
    second = create_trip(client)

    assert client.delete(f"/api/trips/{first['id']}").status_code == 204

    remaining = [t['id'] for t in client.get("/api/trips").json()]
    assert remaining == [second['id']]
