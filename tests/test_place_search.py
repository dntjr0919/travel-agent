from __future__ import annotations

from app.services.map_providers.base import PlaceSearchResult
from app.services import place_search_service
from tests.conftest import register_and_login


def create_trip(client) -> int:
    res = client.post(
        "/api/trips",
        json={
            "title": "장소 검색 테스트 여행",
            "destination": "도쿄",
            "start_date": "2026-11-01",
            "end_date": "2026-11-03",
            "timezone": "Asia/Tokyo",
        },
    )
    assert res.status_code == 201
    return res.json()["id"]


def test_international_place_search_uses_google(client, monkeypatch):
    register_and_login(client, "google-search@example.com")
    trip_id = create_trip(client)

    def fake_google_search(query: str, api_key: str) -> list[PlaceSearchResult]:
        assert query == "tokyo sushi"
        return [
            PlaceSearchResult(
                provider="google",
                external_place_id="google-place-1",
                name="Sushi Example",
                address="Tokyo, Japan",
                latitude=35.6812,
                longitude=139.7671,
                category="restaurant",
                map_url="https://maps.google.com/example",
            )
        ]

    monkeypatch.setattr(
        place_search_service,
        "search_google_places",
        fake_google_search,
    )

    res = client.get(
        f"/api/trips/{trip_id}/places/search",
        params={"scope": "international", "q": "tokyo sushi"},
    )

    assert res.status_code == 200
    data = res.json()

    assert data["provider"] == "google"
    assert data["query"] == "tokyo sushi"
    assert data["results"][0]["name"] == "Sushi Example"


def test_domestic_place_search_uses_kakao(client, monkeypatch):
    register_and_login(client, "kakao-search@example.com")
    trip_id = create_trip(client)

    def fake_kakao_search(query: str, api_key: str) -> list[PlaceSearchResult]:
        assert query == "성수 카페"
        return [
            PlaceSearchResult(
                provider="kakao",
                external_place_id="kakao-place-1",
                name="카페 예시",
                address="서울 성동구",
                latitude=37.544,
                longitude=127.055,
                category="카페",
                map_url="https://map.kakao.com/example",
            )
        ]

    monkeypatch.setattr(
        place_search_service,
        "search_kakao_places",
        fake_kakao_search,
    )

    res = client.get(
        f"/api/trips/{trip_id}/places/search",
        params={"scope": "domestic", "q": "성수 카페"},
    )

    assert res.status_code == 200
    data = res.json()

    assert data["provider"] == "kakao"
    assert data["query"] == "성수 카페"
    assert data["results"][0]["name"] == "카페 예시"


def test_place_search_rejects_invalid_scope_and_short_query(client):
    register_and_login(client, "invalid-search@example.com")
    trip_id = create_trip(client)

    invalid_scope_res = client.get(
        f"/api/trips/{trip_id}/places/search",
        params={"scope": "unknown", "q": "테스트"},
    )
    assert invalid_scope_res.status_code == 422
    assert invalid_scope_res.json()["code"] == "INVALID_PLACE_SEARCH_SCOPE"

    short_query_res = client.get(
        f"/api/trips/{trip_id}/places/search",
        params={"scope": "domestic", "q": "a"},
    )
    assert short_query_res.status_code == 422
    assert short_query_res.json()["code"] == "PLACE_SEARCH_QUERY_TOO_SHORT"


def test_place_search_requires_trip_membership(client):
    register_and_login(client, "owner-search@example.com")
    trip_id = create_trip(client)

    client.post("/api/auth/logout")
    register_and_login(client, "outsider-search@example.com")

    res = client.get(
        f"/api/trips/{trip_id}/places/search",
        params={"scope": "domestic", "q": "성수 카페"},
    )

    assert res.status_code == 403
    assert res.json()["code"] == "FORBIDDEN"