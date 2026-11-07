from __future__ import annotations

import json
from datetime import date
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select

from app.core.errors import AppError
from app.models.itinerary import ItineraryItem
from app.models.user import User
from app.services.external_llm_itinerary_service import (
    GOOGLE_MAPS_HOSTS,
    KAKAO_MAPS_HOSTS,
    NAVER_MAPS_HOSTS,
    extract_json_object_text,
    is_allowed_map_url,
    parse_external_llm_draft,
)
from tests.conftest import register_and_login
from tests.test_invitations import extract_token, invite_member
from tests.test_trips import create_trip


TRIP = SimpleNamespace(
    start_date=date(2026, 11, 1),
    end_date=date(2026, 11, 5),
    timezone="Asia/Seoul",
)


def make_document(*items, version=1) -> str:
    return json.dumps({"version": version, "items": list(items)}, ensure_ascii=False)


def make_item(**overrides) -> dict:
    item = {
        "date": "2026-11-02",
        "start_time": "09:00",
        "title": "박물관 방문",
    }
    item.update(overrides)
    return item


@pytest.mark.parametrize(
    "url",
    [
        "https://google.com/maps/place/example",
        "https://www.google.com/maps/place/example",
        "https://maps.google.com/?q=example",
        "https://goo.gl/maps/example",
        "https://maps.app.goo.gl/example",
    ],
)
def test_google_maps_hosts_are_allowed(url):
    assert is_allowed_map_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://evilgoogle.com/maps",
        "https://google.com.evil.test/maps",
        "https://google.com@evil.test/maps",
        "http://google.com/maps",
        "javascript:alert(1)",
        "data:text/plain,hello",
        "/maps/place/example",
        "https://google.com:8443/maps",
        "https://kakao.com/place/1",
        "https://map.naver.com.evil.test/p/example",
    ],
)
def test_unsafe_or_inactive_map_urls_are_rejected(url):
    assert not is_allowed_map_url(url)


def test_provider_host_lists_enable_google_kakao_and_naver():
    assert GOOGLE_MAPS_HOSTS
    assert KAKAO_MAPS_HOSTS == frozenset({"map.kakao.com", "place.map.kakao.com", "kko.to", "m.map.kakao.com"})
    assert NAVER_MAPS_HOSTS == frozenset({"map.naver.com", "m.map.naver.com", "naver.me"})
    assert is_allowed_map_url("https://map.kakao.com/link/map/1", "kakao")
    assert is_allowed_map_url("https://map.naver.com/p/example", "naver")
    assert is_allowed_map_url("https://map.kakao.com/link/map/1", "any")
    assert is_allowed_map_url("https://map.naver.com/p/example", "any")


def test_empty_place_url_is_valid():
    result = parse_external_llm_draft(make_document(make_item(place_url="")), TRIP)
    assert result[0].valid
    assert result[0].memo is None


def test_valid_item_and_google_url_are_parsed_without_trusting_map_ids():
    result = parse_external_llm_draft(
        make_document(
            make_item(
                memo="점심",
                place_name="제주 박물관",
                place_url="https://maps.google.com/?q=jeju",
            )
        ),
        TRIP,
    )[0]
    assert result.valid
    assert result.title == "박물관 방문"
    assert result.location_name == "제주 박물관"
    assert result.memo == "점심\n지도: https://maps.google.com/?q=jeju"
    assert result.start_at.isoformat() == "2026-11-02T09:00:00+09:00"
    assert result.end_at.isoformat() == "2026-11-02T10:00:00+09:00"


def test_trip_timezone_is_applied_to_local_times():
    trip = SimpleNamespace(start_date=date(2027, 1, 15), end_date=date(2027, 1, 20), timezone="Asia/Tokyo")
    result = parse_external_llm_draft(
        make_document(make_item(date="2027-01-17", start_time="16:35", end_time="18:30")), trip
    )[0]
    assert result.start_at.isoformat() == "2027-01-17T16:35:00+09:00"


def test_invalid_trip_timezone_is_rejected_without_utc_fallback():
    trip = SimpleNamespace(start_date=date(2027, 1, 15), end_date=date(2027, 1, 20), timezone="Invalid/Zone")
    with pytest.raises(AppError) as exc_info:
        parse_external_llm_draft(make_document(make_item(date="2027-01-17")), trip)
    assert exc_info.value.status_code == 422
    assert exc_info.value.code == "EXTERNAL_LLM_INVALID_TIMEZONE"


def test_fenced_json_is_accepted_and_invalid_json_is_rejected():
    raw = "```json\n" + make_document(make_item()) + "\n```"
    assert parse_external_llm_draft(raw, TRIP)[0].valid
    with pytest.raises(AppError, match="JSON 형식"):
        parse_external_llm_draft('{"version": 1,', TRIP)


@pytest.mark.parametrize(
    "wrapper_template",
    [
        "아래는 요청하신 여행 일정입니다!\n\n{json_doc}\n\n즐거운 여행 되세요!",
        "요청하신 조건(오전 박물관 방문)을 반영했습니다.\n```json\n{json_doc}\n```\n추가 수정이 필요하면 말씀해 주세요.",
        "참고 예시: {{\"note\": \"이 객체는 무시됨\"}}\n실제 결과:\n```\n{json_doc}\n```",
    ],
)
def test_extract_json_object_text_and_parse_draft_ignore_surrounding_prose(wrapper_template):
    doc = make_document(make_item(title="외부 LLM 추출 테스트"))
    raw = wrapper_template.format(json_doc=doc)
    extracted = json.loads(extract_json_object_text(raw))
    assert extracted["version"] == 1
    assert extracted["items"][0]["title"] == "외부 LLM 추출 테스트"
    parsed = parse_external_llm_draft(raw, TRIP)
    assert len(parsed) == 1
    assert parsed[0].valid
    assert parsed[0].title == "외부 LLM 추출 테스트"


def test_deeply_nested_json_is_reported_as_invalid_input():
    raw = "[" * 10_000 + "0" + "]" * 10_000
    with pytest.raises(AppError, match="JSON 형식"):
        parse_external_llm_draft(raw, TRIP)


@pytest.mark.parametrize(
    ("item", "expected_error"),
    [
        (make_item(date="2026-10-31"), "여행 기간"),
        (make_item(start_time="24:00"), "시작 시간"),
        ({"date": "2026-11-02", "start_time": "09:00"}, "제목"),
        (make_item(latitude=33.5), "지원하지 않는 필드"),
        (make_item(place_url="https://google.com.evil.test/"), "HTTPS Google"),
    ],
)
def test_invalid_item_is_reported_without_raising_for_document(item, expected_error):
    result = parse_external_llm_draft(make_document(item), TRIP)
    assert not result[0].valid
    assert expected_error in result[0].error


def test_invalid_item_does_not_block_valid_item_analysis():
    result = parse_external_llm_draft(
        make_document(make_item(start_time="99:00"), make_item(title="정상 일정")),
        TRIP,
    )
    assert [item.valid for item in result] == [False, True]


def test_document_rejects_more_than_two_hundred_items():
    with pytest.raises(AppError, match="최대 200개"):
        parse_external_llm_draft(make_document(*(make_item(title=f"일정 {i}") for i in range(201))), TRIP)


def test_document_accepts_between_thirty_and_two_hundred_items():
    raw = make_document(*(make_item(title=f"일정 {i + 1}") for i in range(45)))
    parsed = parse_external_llm_draft(raw, TRIP)
    assert len(parsed) == 45
    assert all(item.valid for item in parsed)


def test_document_rejects_utf8_payload_over_100_kb():
    raw = make_document(make_item(memo="가" * 35_000))
    with pytest.raises(AppError, match="100KB"):
        parse_external_llm_draft(raw, TRIP)


def test_end_time_default_rolls_over_midnight():
    result = parse_external_llm_draft(
        make_document(make_item(date="2026-11-02", start_time="23:30")),
        TRIP,
    )[0]
    assert result.valid
    assert result.end_at.isoformat() == "2026-11-03T00:30:00+09:00"


def test_item_on_last_trip_day_is_invalid_when_default_end_leaves_trip_range():
    result = parse_external_llm_draft(
        make_document(make_item(date="2026-11-05", start_time="23:30")),
        TRIP,
    )[0]
    assert not result.valid
    assert "종료 시각이 여행 기간" in result.error


def test_top_level_array_json_is_accepted_and_normalized():
    raw = json.dumps(
        [
            {"date": "2026-11-02", "start_time": "09:00", "title": "배열 첫 일정"},
            {"date": "2026-11-02", "start_time": "11:00", "title": "배열 두번째 일정"},
        ],
        ensure_ascii=False,
    )
    result = parse_external_llm_draft(raw, TRIP)
    assert len(result) == 2
    assert result[0].title == "배열 첫 일정"
    assert result[1].title == "배열 두번째 일정"


def test_nested_days_schedule_is_flattened_and_normalized():
    raw = json.dumps(
        {
            "days": [
                {
                    "date": "2026-11-02",
                    "activities": [
                        {
                            "time": "09:00 - 10:30",
                            "activity": "공원 산책",
                            "location": "제주 한림공원",
                            "description": "아침 산책 코스",
                            "place_url": "https://map.kakao.com/link/map/12345",
                        },
                        {
                            "time": "오후 1:30",
                            "name": "성산 흑돼지 식사",
                            "spot": "흑돼지 명가",
                            "tip": "대기 시간 유의",
                        },
                    ],
                },
                {
                    "day": "Day 3",
                    "schedule": [
                        {
                            "title": "카페 방문",
                            "place_name": "바다 카페",
                        }
                    ],
                },
            ]
        },
        ensure_ascii=False,
    )
    result = parse_external_llm_draft(raw, TRIP)
    assert len(result) == 3
    # 1번째 항목
    assert result[0].valid
    assert result[0].title == "공원 산책"
    assert result[0].location_name == "제주 한림공원"
    assert result[0].start_at.strftime("%H:%M") == "09:00"
    assert result[0].end_at.strftime("%H:%M") == "10:30"
    assert result[0].place_url == "https://map.kakao.com/link/map/12345"
    # 2번째 항목
    assert result[1].valid
    assert result[1].title == "성산 흑돼지 식사"
    assert result[1].start_at.strftime("%H:%M") == "13:30"
    # 3번째 항목 (Day 3 -> 2026-11-03)
    assert result[2].valid
    assert result[2].date.isoformat() == "2026-11-03"
    assert result[2].title == "카페 방문"


def test_alias_keys_and_smart_quotes_trailing_commas_are_normalized():
    raw = """
    ```json
    {
      “version”: 1,
      “items”: [
        {
          “date”: “2026.11.02”,
          “time”: “9시”,
          “name”: “스마트 따옴표 일정”,
          “place”: “제주 카페”,
          “notes”: “후행 쉼표 테스트”,
          “url”: “https://map.naver.com/p/entry/place/12345”,
        },
      ]
    }
    ```
    """
    result = parse_external_llm_draft(raw, TRIP)
    assert len(result) == 1
    assert result[0].valid
    assert result[0].title == "스마트 따옴표 일정"
    assert result[0].start_at.strftime("%H:%M") == "09:00"
    assert result[0].location_name == "제주 카페"
    assert result[0].place_url == "https://map.naver.com/p/entry/place/12345"


def test_analyze_endpoint_returns_preview_fields_without_detail_payload(client):
    register_and_login(client, "external-llm-analyze@example.com")
    trip = create_trip(client)
    raw = make_document(make_item(memo="숨겨진 메모", place_name="숨겨진 장소"))

    response = client.post(
        f"/api/trips/{trip['id']}/external-llm-itinerary/analyze",
        json={"raw_json": raw},
    )

    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {
                "index": 0,
                "date": "2026-11-02",
                "title": "박물관 방문",
                "valid": True,
                "error": None,
                "warning": None,
            }
        ]
    }
    assert "숨겨진 메모" not in response.text
    assert "숨겨진 장소" not in response.text


def test_viewer_cannot_analyze_or_import_external_llm_items(client):
    register_and_login(client, "external-llm-owner@example.com")
    trip = create_trip(client)
    invitation = invite_member(client, trip["id"], "external-llm-viewer@example.com", "viewer")
    token = extract_token(invitation["invite_url"])
    client.post("/api/auth/logout")
    register_and_login(client, "external-llm-viewer@example.com")
    client.post(f"/api/invitations/{token}/accept")
    raw = make_document(make_item())

    analyze = client.post(
        f"/api/trips/{trip['id']}/external-llm-itinerary/analyze",
        json={"raw_json": raw},
    )
    import_result = client.post(
        f"/api/trips/{trip['id']}/external-llm-itinerary/import",
        json={"raw_json": raw, "selected_indices": [0]},
    )

    assert analyze.status_code == 403
    assert analyze.json()["code"] == "FORBIDDEN"
    assert import_result.status_code == 403
    assert import_result.json()["code"] == "FORBIDDEN"


@pytest.mark.parametrize("role", ["owner", "editor"])
def test_owner_and_editor_can_import_selected_items_only(client, role):
    email = "external-llm-owner@example.com" if role == "owner" else "external-llm-owner-for-editor@example.com"
    register_and_login(client, email)
    trip = create_trip(client)
    if role == "editor":
        invitation = invite_member(client, trip["id"], "external-llm-editor@example.com", "editor")
        token = extract_token(invitation["invite_url"])
        client.post("/api/auth/logout")
        register_and_login(client, "external-llm-editor@example.com")
        client.post(f"/api/invitations/{token}/accept")
    raw = make_document(
        make_item(title="첫 일정", memo="저장하지 않음"),
        make_item(title="선택 일정", place_url="https://maps.app.goo.gl/example"),
    )

    response = client.post(
        f"/api/trips/{trip['id']}/external-llm-itinerary/import",
        json={"raw_json": raw, "selected_indices": [1]},
    )

    assert response.status_code == 200
    assert response.json()["created_count"] == 1
    assert [item["title"] for item in response.json()["items"]] == ["선택 일정"]
    assert response.json()["items"][0]["memo"] == "지도: https://maps.app.goo.gl/example"
    listed = client.get(f"/api/trips/{trip['id']}/itineraries").json()
    assert [item["title"] for item in listed] == ["선택 일정"]
    assert listed[0]["latitude"] is None
    assert listed[0]["longitude"] is None
    assert listed[0]["external_place_id"] is None
    assert listed[0]["place_provider"] is None


def test_import_revalidates_selected_items_and_accepts_only_valid_subset(client):
    register_and_login(client, "external-llm-mixed@example.com")
    trip = create_trip(client)
    raw = make_document(
        make_item(title="잘못된 일정", latitude=33.5),
        make_item(title="정상 일정", place_name="장소"),
    )

    invalid_import = client.post(
        f"/api/trips/{trip['id']}/external-llm-itinerary/import",
        json={"raw_json": raw, "selected_indices": [0]},
    )
    valid_import = client.post(
        f"/api/trips/{trip['id']}/external-llm-itinerary/import",
        json={"raw_json": raw, "selected_indices": [1], "valid": True, "analysis": [{"valid": True}]},
    )

    assert invalid_import.status_code == 422
    assert valid_import.status_code == 200
    assert [item["title"] for item in valid_import.json()["items"]] == ["정상 일정"]
    assert len(client.get(f"/api/trips/{trip['id']}/itineraries").json()) == 1


def test_import_rejects_duplicate_selected_indices(client):
    register_and_login(client, "external-llm-duplicate@example.com")
    trip = create_trip(client)

    response = client.post(
        f"/api/trips/{trip['id']}/external-llm-itinerary/import",
        json={"raw_json": make_document(make_item()), "selected_indices": [0, 0]},
    )

    assert response.status_code == 422
    assert response.json()["code"] == "EXTERNAL_LLM_INVALID_SELECTION"


def test_batch_save_rolls_back_all_items_when_flush_fails(client, db_session, monkeypatch):
    from app.schemas.itinerary import ItineraryCreate
    from app.services.itinerary_service import create_itineraries

    user_data = register_and_login(client, "external-llm-rollback@example.com")
    trip = create_trip(client)
    user = db_session.get(User, user_data["id"])
    original_flush = db_session.flush

    def flush_then_fail(*args, **kwargs):
        original_flush(*args, **kwargs)
        raise RuntimeError("simulated batch failure")

    monkeypatch.setattr(db_session, "flush", flush_then_fail)
    batch = [
        ItineraryCreate(title="Rollback one"),
        ItineraryCreate(title="Rollback two"),
    ]

    with pytest.raises(RuntimeError, match="simulated batch failure"):
        create_itineraries(db_session, trip["id"], user, batch)

    monkeypatch.setattr(db_session, "flush", original_flush)
    assert db_session.scalar(select(func.count()).select_from(ItineraryItem)) == 0


def test_three_real_llm_samples_analyze_and_import_with_auto_place_candidates(client):
    register_and_login(client, "external-llm-3samples@example.com")
    trip = create_trip(
        client,
        title="간사이 겨울 여행",
        destination="오사카·교토",
        start_date="2027-01-17",
        end_date="2027-01-22",
        timezone="Asia/Tokyo",
    )
    trip_id = trip["id"]
    dates = ["2027-01-17", "2027-01-18", "2027-01-19", "2027-01-20", "2027-01-21", "2027-01-22"]

    # 샘플 1 (Gemini): place_url이 ""인 23개 일정
    gemini_items = [
        {
            "date": dates[i % len(dates)],
            "start_time": f"{9 + (i % 8):02d}:00",
            "end_time": f"{10 + (i % 8):02d}:00",
            "title": f"Gemini 일정 {i + 1}",
            "memo": f"메모 {i + 1}",
            "place_name": f"오사카 명소 {i + 1}",
            "place_url": "",
        }
        for i in range(23)
    ]
    gemini_raw = json.dumps({"version": 1, "items": gemini_items}, ensure_ascii=False)
    gemini_analyze = client.post(
        f"/api/trips/{trip_id}/external-llm-itinerary/analyze",
        json={"raw_json": gemini_raw},
    )
    assert gemini_analyze.status_code == 200
    assert len(gemini_analyze.json()["items"]) == 23
    assert all(item["valid"] for item in gemini_analyze.json()["items"])

    # 샘플 2 (ChatGPT): 표준 Google Maps 검색 URL이 포함된 25개 일정 (일부 장소 중복 포함)
    chatgpt_places = [
        ("간사이 국제공항", "https://www.google.com/maps/search/?api=1&query=Kansai+International+Airport"),
        ("도톤보리", "https://www.google.com/maps/search/?api=1&query=Dotonbori+Osaka"),
        ("오사카 성", "https://www.google.com/maps/search/?api=1&query=Osaka+Castle"),
        ("기요미즈데라", "https://www.google.com/maps/search/?api=1&query=Kiyomizu-dera+Kyoto"),
        ("후시미 이나리 신사", "https://www.google.com/maps/search/?api=1&query=Fushimi+Inari+Taisha"),
    ]
    chatgpt_items = [
        {
            "date": dates[i % len(dates)],
            "start_time": f"{9 + (i % 9):02d}:00",
            "end_time": f"{10 + (i % 9):02d}:00",
            "title": f"ChatGPT 일정 {i + 1}",
            "memo": f"상세 안내 {i + 1}",
            "place_name": chatgpt_places[i % len(chatgpt_places)][0],
            "place_url": chatgpt_places[i % len(chatgpt_places)][1],
        }
        for i in range(25)
    ]
    chatgpt_raw = json.dumps({"version": 1, "items": chatgpt_items}, ensure_ascii=False)
    chatgpt_analyze = client.post(
        f"/api/trips/{trip_id}/external-llm-itinerary/analyze",
        json={"raw_json": chatgpt_raw},
    )
    assert chatgpt_analyze.status_code == 200
    assert len(chatgpt_analyze.json()["items"]) == 25
    assert all(item["valid"] for item in chatgpt_analyze.json()["items"])

    chatgpt_import = client.post(
        f"/api/trips/{trip_id}/external-llm-itinerary/import",
        json={"raw_json": chatgpt_raw, "selected_indices": list(range(25))},
    )
    assert chatgpt_import.status_code == 200
    assert chatgpt_import.json()["created_count"] == 25

    candidates = client.get(f"/api/trips/{trip_id}/place-candidates").json()
    assert len(candidates) == len(chatgpt_places)
    by_name = {c["name"]: c for c in candidates}
    for place_name, place_url in chatgpt_places:
        assert place_name in by_name
        assert by_name[place_name]["map_url"] == place_url
        assert by_name[place_name]["provider"] == "google"

    # 같은 장소를 다시 Import해도 중복 등록되지 않는지 확인
    repeat_import = client.post(
        f"/api/trips/{trip_id}/external-llm-itinerary/import",
        json={"raw_json": chatgpt_raw, "selected_indices": [0, 1]},
    )
    assert repeat_import.status_code == 200
    candidates_after_repeat = client.get(f"/api/trips/{trip_id}/place-candidates").json()
    assert len(candidates_after_repeat) == len(chatgpt_places)

    # 샘플 3 (Perplexity): 28개 일정 + 모바일 복사 시 섞여 들어오는 [1], [2] 인용 각주 및 Citations 푸터
    perplexity_lines = ['{\u200b"version": 1, "items": [']
    for i in range(28):
        comma = "," if i < 27 else ""
        perplexity_lines.append(
            f'{{"date": "{dates[i % len(dates)]}"[1], "start_time": "{9 + (i % 9)}:00", '
            f'"end_time": "{10 + (i % 9):02d}:00", "title": "Perplexity 일정 {i + 1}[1][2]", '
            f'"memo": "현지 팁 {i + 1} [3]", "place_name": "교토 스팟 {i + 1}[1]", '
            f'"place_url": "https://www.google.com/maps/search/?api=1&query=Kyoto+Spot+{i + 1}[2]"}}[1]{comma}'
        )
    perplexity_lines.append("]}[1][2]\n\nCitations:\n[1] https://example.com/1\n[2] https://example.com/2")
    perplexity_raw = "\n".join(perplexity_lines)

    perplexity_analyze = client.post(
        f"/api/trips/{trip_id}/external-llm-itinerary/analyze",
        json={"raw_json": perplexity_raw},
    )
    assert perplexity_analyze.status_code == 200
    assert len(perplexity_analyze.json()["items"]) == 28
    assert all(item["valid"] for item in perplexity_analyze.json()["items"])
    assert perplexity_analyze.json()["items"][0]["title"] == "Perplexity 일정 1"

    perplexity_import = client.post(
        f"/api/trips/{trip_id}/external-llm-itinerary/import",
        json={"raw_json": perplexity_raw, "selected_indices": list(range(28))},
    )
    assert perplexity_import.status_code == 200
    assert perplexity_import.json()["created_count"] == 28


def test_more_than_thirty_items_import_and_kakao_place_candidates(client):
    register_and_login(client, "external-llm-45items@example.com")
    trip = create_trip(client)
    trip_id = trip["id"]

    # 45개 일정 생성 (카카오맵 URL 포함)
    items = [
        {
            "date": "2026-11-02",
            "start_time": f"{9 + (i % 12):02d}:00",
            "end_time": f"{10 + (i % 12):02d}:00",
            "title": f"카카오/국내 일정 {i + 1}",
            "place_name": f"성수동 명소 {i % 5 + 1}",
            "place_url": f"https://map.kakao.com/link/map/{1000 + (i % 5)}",
        }
        for i in range(45)
    ]
    raw = json.dumps({"version": 1, "items": items}, ensure_ascii=False)

    analyze_res = client.post(
        f"/api/trips/{trip_id}/external-llm-itinerary/analyze",
        json={"raw_json": raw},
    )
    assert analyze_res.status_code == 200
    assert len(analyze_res.json()["items"]) == 45
    assert all(it["valid"] for it in analyze_res.json()["items"])

    import_res = client.post(
        f"/api/trips/{trip_id}/external-llm-itinerary/import",
        json={"raw_json": raw, "selected_indices": list(range(45))},
    )
    assert import_res.status_code == 200
    assert import_res.json()["created_count"] == 45

    candidates = client.get(f"/api/trips/{trip_id}/place-candidates").json()
    assert len(candidates) == 5
    for c in candidates:
        assert c["provider"] == "kakao"
        assert "map.kakao.com" in c["map_url"]


def test_multiline_pretty_printed_json_with_crlf_tabs_and_markdown_fences():
    pretty_fenced = (
        "```json\r\n"
        "{\r\n"
        '\t"version": 1,\r\n'
        '\t"items": [\r\n'
        "\t\t{\r\n"
        '\t\t\t"date": "2026-11-02",\r\n'
        '\t\t\t"start_time": "09:00",\r\n'
        '\t\t\t"end_time": "10:30",\r\n'
        '\t\t\t"title": "다중 줄 박물관 방문",\r\n'
        '\t\t\t"memo": "오전 관람",\r\n'
        '\t\t\t"place_name": "국립제주박물관",\r\n'
        '\t\t\t"place_url": "https://map.kakao.com/link/map/12345"\r\n'
        "\t\t},\r\n"
        "\t\t{\r\n"
        '\t\t\t"date": "2026-11-02",\r\n'
        '\t\t\t"start_time": "12:00",\r\n'
        '\t\t\t"title": "다중 줄 점심 식사"\r\n'
        "\t\t}\r\n"
        "\t]\r\n"
        "}\r\n"
        "```"
    )
    extracted = json.loads(extract_json_object_text(pretty_fenced))
    assert len(extracted["items"]) == 2
    parsed = parse_external_llm_draft(pretty_fenced, TRIP)
    assert len(parsed) == 2
    assert all(item.valid for item in parsed)
    assert [item.title for item in parsed] == ["다중 줄 박물관 방문", "다중 줄 점심 식사"]

    prose_multiline_array = (
        "아래는 요청하신 일정입니다.\r\n\r\n"
        "[\r\n"
        "  {\r\n"
        '    "date": "2026-11-02",\r\n'
        '    "start_time": "09:00",\r\n'
        '    "title": "배열 첫 일정"\r\n'
        "  },\r\n"
        "  {\r\n"
        '    "date": "2026-11-02",\r\n'
        '    "start_time": "11:00",\r\n'
        '    "title": "배열 둘째 일정"\r\n'
        "  }\r\n"
        "]\r\n"
        "즐거운 여행 되세요!"
    )
    parsed_array = parse_external_llm_draft(prose_multiline_array, TRIP)
    assert len(parsed_array) == 2
    assert all(item.valid for item in parsed_array)
    assert [item.title for item in parsed_array] == ["배열 첫 일정", "배열 둘째 일정"]


def test_backend_unescapes_markdown_escaped_brackets_braces_and_underscores():
    escaped_raw = (
        r'```json' + "\n"
        r'\{' + "\n"
        r'  "version": 1,' + "\n"
        r'  "items": \[{' + "\n"
        r'    "date": "2026-11-02",' + "\n"
        r'    "start\_time": "09:00",' + "\n"
        r'    "end\_time": "10:30",' + "\n"
        r'    "title": "마크다운 이스케이프 일정",' + "\n"
        r'    "place\_name": "교토 역",' + "\n"
        r'    "place\_url": "https://www.google.com/maps/search/?api=1&query=Kyoto\_Station"' + "\n"
        r'  }\]' + "\n"
        r'\}' + "\n"
        r'```'
    )
    extracted_str = extract_json_object_text(escaped_raw)
    extracted_doc = json.loads(extracted_str)
    assert extracted_doc["version"] == 1
    assert extracted_doc["items"][0]["start_time"] == "09:00"
    assert extracted_doc["items"][0]["place_name"] == "교토 역"

    parsed = parse_external_llm_draft(escaped_raw, TRIP)
    assert len(parsed) == 1
    assert parsed[0].valid
    assert parsed[0].title == "마크다운 이스케이프 일정"
    assert parsed[0].location_name == "교토 역"
    assert parsed[0].place_url == "https://www.google.com/maps/search/?api=1&query=Kyoto_Station"
