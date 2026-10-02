from __future__ import annotations

import json

from tests.conftest import register_and_login
from tests.test_invitations import extract_token, invite_member
from tests.test_trips import create_trip


def _mock_search_places(monkeypatch, results_by_query: dict[str, list[dict]]):
    class DummyResult:
        def __init__(self, payload: dict):
            self.provider = payload.get("provider", "google")
            self.external_place_id = payload.get("external_place_id")
            self.name = payload.get("name")
            self.address = payload.get("address")
            self.latitude = payload.get("latitude")
            self.longitude = payload.get("longitude")
            self.category = payload.get("category")
            self.map_url = payload.get("map_url")
            self.source_url = payload.get("source_url")

    def fake_search_places(scope: str, query: str):
        assert scope == "international"
        payloads = results_by_query.get(query, [])
        return "google", [DummyResult(item) for item in payloads]

    monkeypatch.setattr("app.services.ai_itinerary_service.search_places", fake_search_places)


def _mock_gemini(monkeypatch, responses: list[dict]):
    queue = [json.dumps(item) for item in responses]

    def fake_get_gemini_text_json(*, prompt: str, model_name: str) -> str:
        assert model_name in {"gemini-3.5-flash-lite", "gemini-3.8-flash"}
        assert prompt
        return queue.pop(0)

    monkeypatch.setattr("app.services.ai_itinerary_service.get_gemini_text_json", fake_get_gemini_text_json)


def _setup_editor(client):
    register_and_login(client, "owner-ai-editor@example.com")
    trip = create_trip(client)
    invitation = invite_member(client, trip["id"], "editor-ai@example.com", "editor")
    token = extract_token(invitation["invite_url"])
    client.post("/api/auth/logout")
    register_and_login(client, "editor-ai@example.com")
    client.post(f"/api/invitations/{token}/accept")
    return trip


def _setup_viewer(client):
    register_and_login(client, "owner-ai-viewer@example.com")
    trip = create_trip(client)
    invitation = invite_member(client, trip["id"], "viewer-ai@example.com", "viewer")
    token = extract_token(invitation["invite_url"])
    client.post("/api/auth/logout")
    register_and_login(client, "viewer-ai@example.com")
    client.post(f"/api/invitations/{token}/accept")
    return trip


def _valid_request(model: str = "gemini_flash_lite") -> dict:
    return {
        "style": "미술관과 현지 빵집, 야경을 여유롭게 즐기고 싶어요.",
        "interests": ["culture", "cafe", "night_view"],
        "pace": "relaxed",
        "model": model,
    }


def _search_plan() -> dict:
    return {
        "queries": [
            {"query": "Jeju art museum", "category": "culture"},
            {"query": "Jeju cafe view", "category": "cafe"},
        ]
    }


def _course_plan() -> dict:
    return {
        "days": [
            {
                "date": "2026-11-01",
                "items": [
                    {
                        "external_place_id": "p1",
                        "reason": "첫날 분위기 적응에 좋은 미술관입니다.",
                        "suggested_stay_minutes": 120,
                    }
                ],
            }
        ],
        "warnings": ["혼잡 시간은 사전 확인이 필요합니다."],
    }


def _places_payload() -> dict[str, list[dict]]:
    return {
        "Jeju art museum": [
            {
                "provider": "google",
                "external_place_id": "p1",
                "name": "Jeju Art Center",
                "address": "Jeju",
                "latitude": 33.1,
                "longitude": 126.1,
                "category": "museum",
                "map_url": "https://maps.example/p1",
                "source_url": "https://source.example/p1",
            }
        ],
        "Jeju cafe view": [
            {
                "provider": "google",
                "external_place_id": "p2",
                "name": "Jeju View Cafe",
                "address": "Jeju",
                "latitude": 33.2,
                "longitude": 126.2,
                "category": "cafe",
                "map_url": "https://maps.example/p2",
                "source_url": "https://source.example/p2",
            }
        ],
    }


def test_owner_gets_ai_itinerary_draft_success(client, monkeypatch):
    register_and_login(client, "owner-ai-success@example.com")
    trip = create_trip(client)

    _mock_gemini(monkeypatch, [_search_plan(), _course_plan()])
    _mock_search_places(monkeypatch, _places_payload())

    res = client.post(
        f"/api/trips/{trip['id']}/ai-itinerary-drafts",
        json=_valid_request(),
    )

    assert res.status_code == 200
    data = res.json()
    assert data["destination"] == "Jeju"
    assert data["days"][0]["items"][0]["external_place_id"] == "p1"
    assert data["days"][0]["items"][0]["provider"] == "google"


def test_editor_gets_ai_itinerary_draft_success(client, monkeypatch):
    trip = _setup_editor(client)
    _mock_gemini(monkeypatch, [_search_plan(), _course_plan()])
    _mock_search_places(monkeypatch, _places_payload())

    res = client.post(
        f"/api/trips/{trip['id']}/ai-itinerary-drafts",
        json=_valid_request(),
    )

    assert res.status_code == 200


def test_viewer_is_forbidden(client):
    trip = _setup_viewer(client)

    res = client.post(
        f"/api/trips/{trip['id']}/ai-itinerary-drafts",
        json=_valid_request(),
    )

    assert res.status_code == 403
    assert res.json()["code"] == "FORBIDDEN"


def test_destination_required_returns_422(client):
    register_and_login(client, "owner-ai-no-dest@example.com")
    trip = create_trip(client)
    client.patch(f"/api/trips/{trip['id']}", json={"destination": ""})

    res = client.post(
        f"/api/trips/{trip['id']}/ai-itinerary-drafts",
        json=_valid_request(),
    )

    assert res.status_code == 422
    assert res.json()["code"] == "AI_ITINERARY_DESTINATION_REQUIRED"


def test_style_length_validation(client):
    register_and_login(client, "owner-ai-style@example.com")
    trip = create_trip(client)

    short_res = client.post(
        f"/api/trips/{trip['id']}/ai-itinerary-drafts",
        json={**_valid_request(), "style": "a"},
    )
    assert short_res.status_code == 422
    assert short_res.json()["code"] == "AI_ITINERARY_STYLE_TOO_SHORT"

    long_res = client.post(
        f"/api/trips/{trip['id']}/ai-itinerary-drafts",
        json={**_valid_request(), "style": "a" * 301},
    )
    assert long_res.status_code == 422
    assert long_res.json()["code"] == "AI_ITINERARY_STYLE_TOO_LONG"


def test_invalid_interest_pace_model_return_422(client):
    register_and_login(client, "owner-ai-invalids@example.com")
    trip = create_trip(client)

    interest_res = client.post(
        f"/api/trips/{trip['id']}/ai-itinerary-drafts",
        json={**_valid_request(), "interests": ["culture", "invalid"]},
    )
    assert interest_res.status_code == 422
    assert interest_res.json()["code"] == "AI_ITINERARY_INVALID_INTEREST"

    pace_res = client.post(
        f"/api/trips/{trip['id']}/ai-itinerary-drafts",
        json={**_valid_request(), "pace": "sprint"},
    )
    assert pace_res.status_code == 422
    assert pace_res.json()["code"] == "AI_ITINERARY_INVALID_PACE"

    model_res = client.post(
        f"/api/trips/{trip['id']}/ai-itinerary-drafts",
        json={**_valid_request(), "model": "unknown"},
    )
    assert model_res.status_code == 422
    assert model_res.json()["code"] == "AI_ITINERARY_INVALID_MODEL"


def test_invalid_search_plan_returns_502(client, monkeypatch):
    register_and_login(client, "owner-ai-invalid-plan@example.com")
    trip = create_trip(client)

    _mock_gemini(monkeypatch, [{"queries": [{"query": "museum only", "category": "culture"}]}])

    res = client.post(
        f"/api/trips/{trip['id']}/ai-itinerary-drafts",
        json=_valid_request(),
    )

    assert res.status_code == 502
    assert res.json()["code"] == "AI_ITINERARY_INVALID_SEARCH_PLAN"


def test_google_places_dedup_by_external_id(client, monkeypatch):
    register_and_login(client, "owner-ai-dedup@example.com")
    trip = create_trip(client)

    _mock_gemini(monkeypatch, [_search_plan(), _course_plan()])
    _mock_search_places(
        monkeypatch,
        {
            "Jeju art museum": [
                {
                    "provider": "google",
                    "external_place_id": "p1",
                    "name": "Place A",
                    "address": "Addr",
                    "latitude": 0.0,
                    "longitude": 0.0,
                    "category": "museum",
                    "map_url": None,
                    "source_url": None,
                }
            ],
            "Jeju cafe view": [
                {
                    "provider": "google",
                    "external_place_id": "p1",
                    "name": "Place A duplicate",
                    "address": "Addr2",
                    "latitude": 1.0,
                    "longitude": 1.0,
                    "category": "cafe",
                    "map_url": None,
                    "source_url": None,
                }
            ],
        },
    )

    res = client.post(
        f"/api/trips/{trip['id']}/ai-itinerary-drafts",
        json=_valid_request(),
    )

    assert res.status_code == 200
    item = res.json()["days"][0]["items"][0]
    assert item["name"] == "Place A"


def test_out_of_candidate_id_is_removed(client, monkeypatch):
    register_and_login(client, "owner-ai-out-of-candidate@example.com")
    trip = create_trip(client)

    _mock_gemini(
        monkeypatch,
        [
            _search_plan(),
            {
                "days": [
                    {
                        "date": "2026-11-01",
                        "items": [
                            {
                                "external_place_id": "not-in-candidates",
                                "reason": "없는 장소",
                                "suggested_stay_minutes": 120,
                            }
                        ],
                    }
                ]
            },
        ],
    )
    _mock_search_places(monkeypatch, _places_payload())

    res = client.post(
        f"/api/trips/{trip['id']}/ai-itinerary-drafts",
        json=_valid_request(),
    )

    assert res.status_code == 502
    assert res.json()["code"] == "AI_ITINERARY_INVALID_COURSE_RESPONSE"


def test_filters_out_of_range_duplicates_and_invalid_stay(client, monkeypatch):
    register_and_login(client, "owner-ai-filters@example.com")
    trip = create_trip(client)

    _mock_gemini(
        monkeypatch,
        [
            _search_plan(),
            {
                "days": [
                    {
                        "date": "2026-10-30",
                        "items": [
                            {
                                "external_place_id": "p1",
                                "reason": "기간 밖",
                                "suggested_stay_minutes": 120,
                            }
                        ],
                    },
                    {
                        "date": "2026-11-01",
                        "items": [
                            {
                                "external_place_id": "p1",
                                "reason": "유효 1",
                                "suggested_stay_minutes": 120,
                            },
                            {
                                "external_place_id": "p1",
                                "reason": "중복 제거",
                                "suggested_stay_minutes": 120,
                            },
                            {
                                "external_place_id": "p2",
                                "reason": "유효 2",
                                "suggested_stay_minutes": 90,
                            },
                            {
                                "external_place_id": "p2",
                                "reason": "30분 단위 아님",
                                "suggested_stay_minutes": 95,
                            },
                            {
                                "external_place_id": "p3",
                                "reason": "유효 3",
                                "suggested_stay_minutes": 60,
                            },
                            {
                                "external_place_id": "p4",
                                "reason": "유효 4",
                                "suggested_stay_minutes": 30,
                            },
                            {
                                "external_place_id": "p5",
                                "reason": "5번째는 잘려야 함",
                                "suggested_stay_minutes": 60,
                            },
                        ],
                    },
                    {
                        "date": "2026-11-02",
                        "items": [
                            {
                                "external_place_id": "p1",
                                "reason": "다른 날짜 중복 제거",
                                "suggested_stay_minutes": 120,
                            }
                        ],
                    },
                ]
            },
        ],
    )
    _mock_search_places(
        monkeypatch,
        {
            "Jeju art museum": [
                {
                    "provider": "google",
                    "external_place_id": "p1",
                    "name": "P1",
                    "address": "A",
                    "latitude": 0.0,
                    "longitude": 0.0,
                    "category": "museum",
                    "map_url": None,
                    "source_url": None,
                },
                {
                    "provider": "google",
                    "external_place_id": "p3",
                    "name": "P3",
                    "address": "A",
                    "latitude": 0.0,
                    "longitude": 0.0,
                    "category": "park",
                    "map_url": None,
                    "source_url": None,
                },
                {
                    "provider": "google",
                    "external_place_id": "p4",
                    "name": "P4",
                    "address": "A",
                    "latitude": 0.0,
                    "longitude": 0.0,
                    "category": "food",
                    "map_url": None,
                    "source_url": None,
                },
            ],
            "Jeju cafe view": [
                {
                    "provider": "google",
                    "external_place_id": "p2",
                    "name": "P2",
                    "address": "B",
                    "latitude": 1.0,
                    "longitude": 1.0,
                    "category": "cafe",
                    "map_url": None,
                    "source_url": None,
                },
                {
                    "provider": "google",
                    "external_place_id": "p5",
                    "name": "P5",
                    "address": "C",
                    "latitude": 2.0,
                    "longitude": 2.0,
                    "category": "shop",
                    "map_url": None,
                    "source_url": None,
                },
            ],
        },
    )

    res = client.post(
        f"/api/trips/{trip['id']}/ai-itinerary-drafts",
        json=_valid_request(),
    )

    assert res.status_code == 200
    data = res.json()
    day1 = next(day for day in data["days"] if day["date"] == "2026-11-01")
    assert len(day1["items"]) == 4
    assert day1["items"][0]["external_place_id"] == "p1"

    day2 = next(day for day in data["days"] if day["date"] == "2026-11-02")
    assert day2["items"] == []


def test_no_valid_course_items_returns_502(client, monkeypatch):
    register_and_login(client, "owner-ai-no-valid-items@example.com")
    trip = create_trip(client)

    _mock_gemini(
        monkeypatch,
        [
            _search_plan(),
            {
                "days": [
                    {
                        "date": "2026-11-01",
                        "items": [
                            {
                                "external_place_id": "p1",
                                "reason": "",
                                "suggested_stay_minutes": 120,
                            }
                        ],
                    }
                ]
            },
        ],
    )
    _mock_search_places(monkeypatch, _places_payload())

    res = client.post(
        f"/api/trips/{trip['id']}/ai-itinerary-drafts",
        json=_valid_request(),
    )

    assert res.status_code == 502
    assert res.json()["code"] == "AI_ITINERARY_INVALID_COURSE_RESPONSE"
