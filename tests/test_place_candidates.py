from __future__ import annotations

from tests.conftest import login, register_and_login


def create_trip(client) -> int:
    res = client.post(
        "/api/trips",
        json={
            "title": "장소 후보 테스트 여행",
            "destination": "서울",
            "start_date": "2026-11-01",
            "end_date": "2026-11-03",
            "timezone": "Asia/Seoul",
        },
    )
    assert res.status_code == 201
    return res.json()["id"]


def candidate_payload(external_place_id: str = "place-001") -> dict:
    return {
        "provider": "manual-test",
        "external_place_id": external_place_id,
        "name": "테스트 장소",
        "address": "서울특별시 테스트구 테스트로 1",
        "latitude": 37.5665,
        "longitude": 126.9780,
        "category": "restaurant",
        "map_url": "https://example.com/map",
        "source_url": "https://example.com/source",
        "memo": "방문 후보",
    }


def test_owner_can_create_list_update_and_delete_place_candidate(client):
    register_and_login(client, "owner@example.com", display_name="Owner")
    trip_id = create_trip(client)

    create_res = client.post(
        f"/api/trips/{trip_id}/place-candidates",
        json=candidate_payload(),
    )
    assert create_res.status_code == 201

    candidate = create_res.json()
    candidate_id = candidate["id"]

    assert candidate["trip_id"] == trip_id
    assert candidate["name"] == "테스트 장소"
    assert candidate["created_by_name"] == "Owner"

    list_res = client.get(f"/api/trips/{trip_id}/place-candidates")
    assert list_res.status_code == 200
    assert len(list_res.json()) == 1

    update_res = client.patch(
        f"/api/place-candidates/{candidate_id}",
        json={"memo": "점심 시간에 방문"},
    )
    assert update_res.status_code == 200
    assert update_res.json()["memo"] == "점심 시간에 방문"

    delete_res = client.delete(f"/api/place-candidates/{candidate_id}")
    assert delete_res.status_code == 204

    list_res = client.get(f"/api/trips/{trip_id}/place-candidates")
    assert list_res.status_code == 200
    assert list_res.json() == []


def test_duplicate_place_candidate_returns_conflict(client):
    register_and_login(client, "duplicate@example.com")
    trip_id = create_trip(client)

    first_res = client.post(
        f"/api/trips/{trip_id}/place-candidates",
        json=candidate_payload("same-place"),
    )
    assert first_res.status_code == 201

    second_res = client.post(
        f"/api/trips/{trip_id}/place-candidates",
        json=candidate_payload("same-place"),
    )
    assert second_res.status_code == 409
    assert second_res.json()["code"] == "PLACE_CANDIDATE_ALREADY_EXISTS"


def test_viewer_can_list_but_cannot_modify_place_candidates(client):
    register_and_login(client, "owner2@example.com", display_name="Owner2")
    trip_id = create_trip(client)

    create_res = client.post(
        f"/api/trips/{trip_id}/place-candidates",
        json=candidate_payload(),
    )
    assert create_res.status_code == 201
    candidate_id = create_res.json()["id"]

    client.post("/api/auth/logout")

    register_and_login(client, "viewer@example.com", display_name="Viewer")

    client.post("/api/auth/logout")
    login(client, "owner2@example.com")

    invite_res = client.post(
        f"/api/trips/{trip_id}/invitations",
        json={
            "email": "viewer@example.com",
            "role": "viewer",
        },
    )
    assert invite_res.status_code == 201

    invite_token = invite_res.json()["invite_url"].rstrip("/").split("/")[-1]

    client.post("/api/auth/logout")
    login(client, "viewer@example.com")

    accept_res = client.post(f"/api/invitations/{invite_token}/accept")
    assert accept_res.status_code == 200

    list_res = client.get(f"/api/trips/{trip_id}/place-candidates")
    assert list_res.status_code == 200
    assert len(list_res.json()) == 1

    create_res = client.post(
        f"/api/trips/{trip_id}/place-candidates",
        json=candidate_payload("viewer-new-place"),
    )
    assert create_res.status_code == 403

    update_res = client.patch(
        f"/api/place-candidates/{candidate_id}",
        json={"memo": "Viewer가 수정 시도"},
    )
    assert update_res.status_code == 403

    delete_res = client.delete(f"/api/place-candidates/{candidate_id}")
    assert delete_res.status_code == 403