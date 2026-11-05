from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from app.core.config import get_settings
from app.core.presence import TripPresenceManager, presence_manager
from tests.conftest import register_and_login
from tests.test_trips import create_trip


def test_saved_place_candidate_pagination_slices_twelve_candidates_into_expected_pages():
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required to execute the inline pagination helper")

    template_path = Path(__file__).parents[1] / "app" / "templates" / "trip_detail.html"
    template = template_path.read_text(encoding="utf-8")
    page_size_start = template.index("const PLACE_CANDIDATE_PAGE_SIZE = ")
    page_size_end = template.index("\n", page_size_start)
    page_size_source = template[page_size_start:page_size_end]
    helper_start = template.index("function getPlaceCandidatePage(")
    helper_end = template.index("\nfunction renderPlaceCandidates(", helper_start)
    helper_source = template[helper_start:helper_end]
    script = f"""
{page_size_source}
{helper_source}
const candidates = Array.from({{ length: 12 }}, (_, index) => ({{ name: `place-${{index + 1}}` }}));
const pages = [1, 2, 3].map((pageNumber) => {{
  const page = getPlaceCandidatePage(candidates, pageNumber);
  return {{
    range: `${{page.startIndex + 1}}–${{page.endIndex}} / 총 ${{candidates.length}}개`,
    names: page.visibleCandidates.map((candidate) => candidate.name),
  }};
}});
process.stdout.write(JSON.stringify(pages));
"""
    result = subprocess.run(
        [node, "--input-type=commonjs", "-e", script],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert json.loads(result.stdout) == [
        {
            "range": "1–5 / 총 12개",
            "names": [f"place-{index}" for index in range(1, 6)],
        },
        {
            "range": "6–10 / 총 12개",
            "names": [f"place-{index}" for index in range(6, 11)],
        },
        {
            "range": "11–12 / 총 12개",
            "names": [f"place-{index}" for index in range(11, 13)],
        },
    ]


def test_frontend_extract_json_object_helper_handles_prose_and_code_fences():
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required to execute the inline JSON extractor helper")

    template_path = Path(__file__).parents[1] / "app" / "templates" / "trip_detail.html"
    template = template_path.read_text(encoding="utf-8")
    helper_start = template.index("function extractJsonObjectFromLlmText(")
    helper_end = template.index("\nfunction setExternalLlmFeedback(", helper_start)
    helper_source = template[helper_start:helper_end]
    samples = [
        '아래는 생성된 일정입니다.\n```json\n{"version":1,"items":[{"title":"테스트"}]}\n```\n즐거운 여행 되세요!',
        '설명 텍스트 {"kind":"flight","title":"KE703"} 꼬리말',
    ]
    script = f"""
{helper_source}
const samples = {json.dumps(samples, ensure_ascii=False)};
const parsed = samples.map((raw) => extractJsonObjectFromLlmText(raw));
process.stdout.write(JSON.stringify(parsed));
"""
    result = subprocess.run(
        [node, "--input-type=commonjs", "-e", script],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert json.loads(result.stdout) == [
        {"version": 1, "items": [{"title": "테스트"}]},
        {"kind": "flight", "title": "KE703"},
    ]


def test_presence_manager_broadcast_trip_activity():
    class DummyWebSocket:
        def __init__(self, should_fail: bool = False):
            self.should_fail = should_fail
            self.messages: list[dict] = []

        async def send_json(self, message: dict) -> None:
            if self.should_fail:
                raise RuntimeError("socket closed")
            self.messages.append(message)

    manager = TripPresenceManager()
    healthy_ws = DummyWebSocket()
    dead_ws = DummyWebSocket(should_fail=True)
    manager._connections[77][1].add(healthy_ws)
    manager._connections[77][2].add(dead_ws)
    manager._users[77][1] = {"id": 1, "display_name": "Alice"}
    manager._users[77][2] = {"id": 2, "display_name": "Bob"}

    coro = manager.broadcast_trip_activity(
        77,
        actor_id=2,
        actor_name="Bob",
        entity_type="itinerary",
        action="created",
        entity_id=101,
        title="우에노 공원 산책",
    )
    try:
        coro.send(None)
    except StopIteration:
        pass

    assert len(healthy_ws.messages) == 1
    payload = healthy_ws.messages[0]
    assert payload["type"] == "trip_activity"
    assert payload["trip_id"] == 77
    assert payload["actor_id"] == 2
    assert payload["actor_name"] == "Bob"
    assert payload["entity_type"] == "itinerary"
    assert payload["action"] == "created"
    assert payload["entity_id"] == 101
    assert payload["title"] == "우에노 공원 산책"
    assert payload["timestamp"]
    assert 2 not in manager._connections[77]


def test_collaborator_entity_mutations_broadcast_trip_activity(client, monkeypatch):
    events: list[dict] = []

    async def record_activity(trip_id: int, **kwargs) -> None:
        events.append({"trip_id": trip_id, **kwargs})

    monkeypatch.setattr(presence_manager, "broadcast_trip_activity", record_activity)

    register_and_login(client, "activity-broadcast@example.com")
    trip = create_trip(client)
    trip_id = trip["id"]

    itinerary_res = client.post(
        f"/api/trips/{trip_id}/itineraries",
        json={"title": "첫 일정"},
    )
    assert itinerary_res.status_code == 201
    itinerary_data = itinerary_res.json()
    itinerary_id = itinerary_data["id"]

    patch_itinerary_res = client.patch(
        f"/api/itineraries/{itinerary_id}",
        json={"title": "수정된 일정", "version": itinerary_data["version"]},
    )
    assert patch_itinerary_res.status_code == 200

    place_res = client.post(
        f"/api/trips/{trip_id}/place-candidates",
        json={"provider": "google", "external_place_id": "place-sensoji-1", "name": "센소지"},
    )
    assert place_res.status_code == 201
    place_id = place_res.json()["id"]

    patch_place_res = client.patch(
        f"/api/place-candidates/{place_id}",
        json={"memo": "오전 방문"},
    )
    assert patch_place_res.status_code == 200

    booking_res = client.post(
        f"/api/trips/{trip_id}/booking-candidates",
        json={"kind": "accommodation", "title": "도쿄 호텔", "accommodation_name": "도쿄 호텔"},
    )
    assert booking_res.status_code == 201
    booking_id = booking_res.json()["id"]

    patch_booking_res = client.patch(
        f"/api/booking-candidates/{booking_id}",
        json={"title": "도쿄 시티 호텔"},
    )
    assert patch_booking_res.status_code == 200

    summary = [(e["entity_type"], e["action"], e["entity_id"], e["title"]) for e in events]
    assert summary == [
        ("itinerary", "created", itinerary_id, "첫 일정"),
        ("itinerary", "updated", itinerary_id, "수정된 일정"),
        ("place_candidate", "created", place_id, "센소지"),
        ("place_candidate", "updated", place_id, "센소지"),
        ("booking_candidate", "created", booking_id, "도쿄 호텔"),
        ("booking_candidate", "updated", booking_id, "도쿄 시티 호텔"),
    ]


def test_auth_pages_preserve_forms_fields_and_navigation(client):
    pages = {
        "/login": (
            'id="login-form"',
            'name="email"',
            'name="password"',
            'href="/register"',
            'href="/forgot-password"',
        ),
        "/register": (
            'id="register-form"',
            'name="email"',
            'name="display_name"',
            'name="password"',
            'href="/login"',
        ),
        "/forgot-password": (
            'id="forgot-form"',
            'name="email"',
            'id="forgot-error"',
            'id="forgot-result"',
            'href="/login"',
        ),
        "/reset-password/test-token": (
            'id="reset-form"',
            'name="new_password"',
            'name="confirm_password"',
            'id="reset-error"',
            'id="reset-success"',
            'href="/login"',
        ),
    }

    for path, expected_markup in pages.items():
        res = client.get(path)

        assert res.status_code == 200
        for expected in expected_markup:
            assert expected in res.text


def test_base_navigation_preserves_brand_and_logout_contract(client):
    res = client.get("/login")

    assert res.status_code == 200
    assert 'class="brand" href="/trips"' in res.text
    assert 'href="/login">로그인</a>' in res.text
    assert 'href="/register">회원가입</a>' in res.text
    assert 'id="nav-user" class="nav-user"' in res.text
    assert '<button id="nav-logout" class="link-button" style="display:none">로그아웃</button>' in res.text


def test_trip_detail_redirects_to_login_when_not_authenticated(client):
    res = client.get("/trips/1", follow_redirects=False)

    assert res.status_code in {302, 307}
    assert res.headers.get("location") == "/login"


def test_trip_detail_returns_200_for_authenticated_user(client):
    register_and_login(client, "pages-auth@example.com")
    trip = create_trip(client)

    res = client.get(f"/trips/{trip['id']}")

    assert res.status_code == 200
    assert "text/html" in res.headers.get("content-type", "")


def test_trip_list_page_preserves_list_and_create_links(client):
    register_and_login(client, "pages-trip-list@example.com")

    res = client.get("/trips")

    assert res.status_code == 200
    assert "내 여행" in res.text
    assert "새 여행 만들기" in res.text
    assert 'href="/trips/new"' in res.text
    assert 'id="trip-list"' in res.text
    assert 'id="trip-empty"' in res.text
    assert 'href="/trips/${t.id}"' in res.text
    assert 'owner: "Owner", editor: "Editor", viewer: "Viewer"' in res.text


def test_trip_form_page_preserves_fields_and_error_region(client):
    register_and_login(client, "pages-trip-form@example.com")

    res = client.get("/trips/new")

    assert res.status_code == 200
    assert "새 여행 만들기" in res.text
    assert 'id="trip-form"' in res.text
    assert 'name="title"' in res.text
    assert 'name="destination"' in res.text
    assert 'id="trip-start-date" name="start_date" required' in res.text
    assert 'id="trip-end-date" name="end_date" required' in res.text
    assert 'name="timezone"' in res.text
    assert 'id="trip-error"' in res.text


def test_trip_detail_contains_unified_map_and_layout_markup(client):
    register_and_login(client, "pages-unified-map-markup@example.com")
    trip = create_trip(client)

    res = client.get(f"/trips/{trip['id']}")

    assert res.status_code == 200
    text = res.text
    assert 'id="travel-map"' in text
    assert 'id="saved-candidates-map-filter"' in text
    assert 'id="trip-tools-drawer"' in text
    assert 'id="trip-tools-backdrop"' in text
    assert 'id="trip-tools-tabs"' in text
    assert 'id="trip-header"' in text
    assert 'class="page-header trip-header"' in text
    assert 'id="open-tools-btn"' in text
    assert 'class="trip-tools-toggle"' in text
    assert 'class="sidebar-toggle-icon"' in text
    assert 'class="trip-header-main"' in text
    assert 'class="trip-header-info"' in text
    assert 'class="trip-header-controls"' in text
    assert 'class="header-actions trip-header-actions"' in text
    assert 'id="edit-trip-btn"' in text
    assert 'id="add-item-btn"' in text
    assert 'id="presence-bar"' in text
    assert 'id="presence-users"' in text
    assert 'aria-controls="trip-tools-drawer"' in text
    assert 'id="trip-tools-tab-places"' in text
    assert 'id="trip-tools-tab-ai"' in text
    assert 'id="trip-tools-tab-reservations"' in text
    for tab_name in ("places", "ai", "reservations"):
        assert f'data-tools-tab="{tab_name}"' in text
    assert text.count('role="tab"') == 3
    assert 'id="external-llm-prompt"' in text
    assert 'id="external-llm-copy-prompt-btn"' in text
    assert 'id="external-llm-json"' in text
    assert 'id="external-llm-analyze-btn"' in text
    assert 'id="external-llm-results"' in text
    assert 'id="external-llm-import-btn"' in text
    assert "여행 준비 센터" in text
    assert "AI 일정" in text
    assert 'id="trip-tools-tab-reservations"' in text
    assert 'id="trip-tools-panel-places"' in text
    assert 'id="trip-tools-panel-ai"' in text
    assert 'id="trip-tools-panel-reservations"' in text
    assert 'id="ai-draft-accordion-toggle"' in text
    assert 'aria-controls="ai-draft-accordion-content"' in text
    assert 'id="ai-draft-accordion-content" class="tool-accordion-content" hidden' in text
    assert 'id="external-llm-accordion-toggle"' in text
    assert 'aria-controls="external-llm-accordion-content"' in text
    assert 'id="external-llm-accordion-content" class="tool-accordion-content" hidden' in text
    assert 'id="reservation-transport-accordion-toggle"' in text
    assert 'id="reservation-transport-accordion-content" class="tool-accordion-content" hidden' in text
    assert 'id="reservation-analysis-accordion-toggle"' in text
    assert 'aria-controls="reservation-analysis-accordion-content"' in text
    assert 'id="reservation-analysis-accordion-content" class="tool-accordion-content" hidden' in text
    assert 'id="reservation-add-accordion-toggle"' in text
    assert 'aria-controls="reservation-add-accordion-content"' in text
    assert 'id="reservation-add-accordion-content" class="tool-accordion-content" hidden' in text
    assert 'id="reservation-accommodation-accordion-toggle"' in text
    assert 'id="reservation-accommodation-accordion-content" class="tool-accordion-content" hidden' in text
    assert '<span>예약 정보 분석</span>' in text
    assert '<span>예약 후보 추가</span>' in text
    assert '<span>교통 후보 보관함</span>' in text
    assert '<span>숙박 후보 보관함</span>' in text
    reservation_add_start = text.index('id="reservation-add-accordion-content"')
    reservation_transport_start = text.index('id="reservation-transport-accordion-toggle"', reservation_add_start)
    reservation_add_content = text[reservation_add_start:reservation_transport_start]
    assert 'id="travel-booking-candidate-form"' in reservation_add_content
    assert '<select name="kind" required>' in reservation_add_content
    assert 'id="travel-booking-candidate-add-btn"' in reservation_add_content
    assert 'id="travel-booking-candidate-error"' in reservation_add_content
    for interest in ("culture", "cafe", "nature", "shopping", "food", "night_view"):
        assert f'name="interests" value="{interest}"' in text
    assert 'id="external-llm-selection-count"' in text
    assert 'id="external-llm-select-all-btn"' in text
    assert 'id="external-llm-deselect-all-btn"' in text
    assert 'id="place-search-pagination"' in text
    assert 'id="place-search-prev-btn"' in text
    assert 'id="place-search-next-btn"' in text
    assert 'id="place-candidate-pagination"' in text
    assert 'id="place-candidate-prev-btn"' in text
    assert 'id="place-candidate-next-btn"' in text
    assert "const PLACE_CANDIDATE_PAGE_SIZE = 5;" in text
    assert "getPlaceCandidatePage(currentPlaceCandidates, placeCandidateCurrentPage)" in text
    assert "visibleCandidates: candidates.slice(startIndex, endIndex)" in text
    assert "placeCandidateCurrentPage = 1;" in text
    assert 'class="reservation-tool-section reservation-import-section"' in text
    assert 'id="reservation-import-heading"' in text
    assert 'id="reservation-image-form"' in text
    assert 'id="external-booking-form"' in text
    assert 'id="travel-booking-candidate-panel"' in text
    assert 'id="travel-booking-transport-heading"' in text
    assert 'id="travel-booking-accommodation-heading"' in text
    assert 'id="travel-booking-transport-list"' in text
    assert 'id="travel-booking-accommodation-list"' in text
    assert 'id="travel-booking-transport-empty"' in text
    assert 'id="travel-booking-accommodation-empty"' in text
    assert 'id="reservation-analysis-save-candidate-btn"' in text
    assert 'id="reservation-analysis-save-candidate-success"' in text
    assert 'id="reservation-analysis-save-candidate-error"' in text
    assert 'id="ai-itinerary-route-btn"' in text
    assert 'id="ai-itinerary-result"' in text
    assert text.index('id="ai-itinerary-result"') < text.index('id="ai-itinerary-route-btn"')
    assert "add-booking-candidate-to-itinerary-btn" in text
    assert "edit-travel-booking-candidate-btn" in text
    assert "delete-travel-booking-candidate-btn" in text
    assert 'id="trip-mobile-tabs"' in text
    assert 'id="trip-mobile-tab-schedule"' in text
    assert 'id="trip-mobile-tab-map"' in text
    assert 'id="item-form-cancel"' in text
    assert 'id="trip-edit-cancel"' in text
    assert 'id="quick-time-edit-panel"' in text
    assert 'id="quick-time-edit-form"' in text
    assert 'id="quick-time-edit-start-at"' in text
    assert 'id="quick-time-edit-end-at"' in text
    assert 'id="quick-time-edit-cancel"' in text
    assert 'id="quick-time-edit-error"' in text
    assert "quick-time-edit-btn" in text
    assert 'id="item-place-search-toggle-btn"' in text
    assert 'id="item-place-search-panel"' in text
    assert 'id="item-place-search-query"' in text
    assert 'id="item-place-search-results"' in text
    assert 'id="travel-map-itinerary-controls"' in text
    assert 'id="travel-map-candidate-controls"' in text
    assert 'id="travel-map-ai-controls"' in text
    assert 'class="item-summary"' in text
    assert 'class="item-time-stack"' in text
    assert 'class="item-time item-time-start"' in text
    assert 'class="item-time item-time-end"' in text
    assert 'class="item-details"' in text
    assert "place-candidate-address" in text
    assert "place-candidate-meta" in text
    assert 'class="place-candidate-secondary-actions"' in text
    assert 'class="item-menu-trigger' in text
    assert 'class="item-action-menu"' in text
    assert 'aria-expanded="false"' in text
    assert 'id="ai-itinerary-map"' not in text
    assert 'id="saved-candidates-map"' not in text


def test_trip_detail_contains_collab_and_external_llm_feature_markup(client):
    register_and_login(client, "pages-collab-external-llm@example.com")
    trip = create_trip(client)

    res = client.get(f"/trips/{trip['id']}")

    assert res.status_code == 200
    text = res.text
    assert 'id="enable-push-notifications-btn"' in text
    assert 'id="trip-activity-toast"' in text
    assert 'id="open-tools-unread-dot"' in text
    assert 'id="open-tools-floating-unread-dot"' in text
    assert 'id="trip-tools-tab-places-unread-dot"' in text
    assert 'id="trip-tools-tab-reservations-unread-dot"' in text
    assert 'id="reservation-transport-unread-dot"' in text
    assert 'id="reservation-accommodation-unread-dot"' in text
    assert 'id="external-llm-custom-request"' in text
    assert 'id="external-llm-share-prompt-btn"' in text
    assert 'id="reservation-external-llm-custom-request"' in text
    assert 'id="reservation-external-llm-copy-btn"' in text
    assert 'id="reservation-external-llm-share-btn"' in text
    assert 'id="reservation-external-llm-json"' in text
    assert 'id="reservation-external-llm-apply-btn"' in text
    assert 'id="reservation-external-llm-feedback"' in text
    assert "const PUSH_NOTIFICATION_COOLDOWN_MS = 3600 * 1000;" in text
    assert 'const PUSH_NOTIFICATION_ENABLED_STORAGE_KEY = "travel_planner_push_enabled";' in text
    assert 'aria-pressed="false"' in text
    assert "function isPushNotificationEnabled(" in text
    assert "function setPushNotificationEnabled(" in text
    assert "function extractJsonObjectFromLlmText(" in text
    assert "function normalizeExternalLlmJsonForRequest(" in text
    assert "function buildReservationExternalLlmPrompt(" in text
    assert "async function handleTripActivityEvent(" in text
    assert "function updateUnreadIndicators(" in text

    css_path = Path(__file__).parents[1] / "app" / "static" / "css" / "app.css"
    css_text = css_path.read_text(encoding="utf-8")
    assert "@media (min-width: 761px)" not in css_text


def test_frontend_normalize_external_llm_json_preserves_valid_place_url_and_clears_invalid_urls(client):
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required to execute the inline JSON normalizer helper")

    template_path = Path(__file__).parents[1] / "app" / "templates" / "trip_detail.html"
    template = template_path.read_text(encoding="utf-8")
    helper_start = template.index("function extractJsonObjectFromLlmText(")
    helper_end = template.index("\nfunction setExternalLlmFeedback(", helper_start)
    helper_source = template[helper_start:helper_end]

    raw_input = (
        '{"version":1,"items":['
        '{"date":"2026-11-02","start_time":"9:00","end_time":"10:30","title":"간사이 공항 도착[1]",'
        '"memo":"입국 심사[2]","place_name":"간사이 국제공항[1]",'
        '"place_url":"https://www.google.com/maps/search/?api=1&query=Kansai+International+Airport","extra_field":"ignored"},'
        '{"date":"2026-11-02","start_time":"12:00","title":"깨진 링크 일정",'
        '"place_name":"도톤보리","place_url":"not-a-url"},'
        '{"date":"2026-11-02","start_time":"15:00","title":"비허용 도메인 일정",'
        '"place_name":"오사카 성","place_url":"http://unsafe.example.com/map"}'
        ']}[1]\n\nCitations:\n[1] https://example.com'
    )
    script = f"""
{helper_source}
const raw = {json.dumps(raw_input, ensure_ascii=False)};
process.stdout.write(normalizeExternalLlmJsonForRequest(raw));
"""
    result = subprocess.run(
        [node, "--input-type=commonjs", "-e", script],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    normalized_str = result.stdout
    normalized_doc = json.loads(normalized_str)
    assert normalized_doc["items"][0]["start_time"] == "09:00"
    assert normalized_doc["items"][0]["title"] == "간사이 공항 도착"
    assert normalized_doc["items"][0]["place_name"] == "간사이 국제공항"
    assert (
        normalized_doc["items"][0]["place_url"]
        == "https://www.google.com/maps/search/?api=1&query=Kansai+International+Airport"
    )
    assert "extra_field" not in normalized_doc["items"][0]
    assert normalized_doc["items"][1]["place_url"] == ""
    assert normalized_doc["items"][2]["place_url"] == ""

    register_and_login(client, "pages-normalized-import@example.com")
    trip = create_trip(client)
    import_res = client.post(
        f"/api/trips/{trip['id']}/external-llm-itinerary/import",
        json={"raw_json": normalized_str, "selected_indices": [0, 1, 2]},
    )
    assert import_res.status_code == 200
    assert import_res.json()["created_count"] == 3
    candidates = client.get(f"/api/trips/{trip['id']}/place-candidates").json()
    assert len(candidates) == 3
    by_name = {c["name"]: c for c in candidates}
    assert (
        by_name["간사이 국제공항"]["map_url"]
        == "https://www.google.com/maps/search/?api=1&query=Kansai+International+Airport"
    )


def test_trip_detail_renders_google_maps_script_when_browser_key_is_set(client):
    settings = get_settings()
    original_browser_key = settings.google_maps_browser_api_key
    original_server_key = settings.google_maps_api_key

    register_and_login(client, "pages-map-key-on@example.com")
    trip = create_trip(client)

    try:
        settings.google_maps_browser_api_key = "dummy-browser-key"
        settings.google_maps_api_key = "dummy-server-key"

        res = client.get(f"/trips/{trip['id']}")
    finally:
        settings.google_maps_browser_api_key = original_browser_key
        settings.google_maps_api_key = original_server_key

    assert res.status_code == 200
    text = res.text
    assert "https://maps.googleapis.com/maps/api/js?key=dummy-browser-key" in text
    assert "callback=initAiItineraryMap" in text
    assert text.count("https://maps.googleapis.com/maps/api/js?key=") == 1


def test_trip_detail_does_not_render_google_maps_script_when_browser_key_is_empty(client):
    settings = get_settings()
    original_browser_key = settings.google_maps_browser_api_key
    original_server_key = settings.google_maps_api_key

    register_and_login(client, "pages-map-key-off@example.com")
    trip = create_trip(client)

    try:
        settings.google_maps_browser_api_key = ""
        settings.google_maps_api_key = "dummy-server-key"

        res = client.get(f"/trips/{trip['id']}")
    finally:
        settings.google_maps_browser_api_key = original_browser_key
        settings.google_maps_api_key = original_server_key

    assert res.status_code == 200
    assert "maps.googleapis.com/maps/api/js?key=" not in res.text


def test_trip_detail_never_exposes_server_google_maps_api_key(client):
    settings = get_settings()
    original_browser_key = settings.google_maps_browser_api_key
    original_server_key = settings.google_maps_api_key

    register_and_login(client, "pages-map-server-key@example.com")
    trip = create_trip(client)

    try:
        settings.google_maps_browser_api_key = "dummy-browser-key"
        settings.google_maps_api_key = "dummy-server-key"

        res = client.get(f"/trips/{trip['id']}")
    finally:
        settings.google_maps_browser_api_key = original_browser_key
        settings.google_maps_api_key = original_server_key

    assert res.status_code == 200
    assert "dummy-server-key" not in res.text


def test_trip_detail_keeps_inline_js_inside_script_tag(client):
    settings = get_settings()
    original_browser_key = settings.google_maps_browser_api_key

    register_and_login(client, "pages-inline-script-guard@example.com")
    trip = create_trip(client)

    try:
        settings.google_maps_browser_api_key = "dummy-browser-key"
        res = client.get(f"/trips/{trip['id']}")
    finally:
        settings.google_maps_browser_api_key = original_browser_key

    assert res.status_code == 200
    text = res.text

    marker = "const reservationImageFileInput = document.getElementById(\"reservation-image-file\");"
    inline_script_start = text.find("<script>")
    inline_script_end = text.rfind("</script>")
    marker_index = text.find(marker)

    assert inline_script_start != -1
    assert inline_script_end != -1
    assert marker_index != -1
    assert inline_script_start < marker_index < inline_script_end


def test_trip_detail_contains_itinerary_map_link_helpers(client):
    register_and_login(client, "pages-map-link@example.com")
    trip = create_trip(client)

    res = client.get(f"/trips/{trip['id']}")

    assert res.status_code == 200
    assert "function focusItineraryCard(" in res.text
    assert "function focusItineraryMarker(" in res.text
    assert "is-map-focused" in res.text
    assert 'id="mobile-itinerary-map-detail"' in res.text
    assert 'id="mobile-itinerary-map-detail-close-btn"' in res.text
    assert 'id="mobile-itinerary-map-detail-open-schedule-btn"' in res.text
    assert "function showMobileItineraryDetail(" in res.text


def test_trip_detail_places_maps_script_after_inline_script(client):
    settings = get_settings()
    original_browser_key = settings.google_maps_browser_api_key

    register_and_login(client, "pages-script-order@example.com")
    trip = create_trip(client)

    try:
        settings.google_maps_browser_api_key = "dummy-browser-key"
        res = client.get(f"/trips/{trip['id']}")
    finally:
        settings.google_maps_browser_api_key = original_browser_key

    assert res.status_code == 200
    text = res.text

    maps_script_index = text.find("https://maps.googleapis.com/maps/api/js?key=dummy-browser-key")
    assert maps_script_index != -1

    maps_script_tag_open_index = text.rfind("<script", 0, maps_script_index)
    assert maps_script_tag_open_index != -1

    inline_script_start = text.find("<script>")
    inline_script_end = text.find("</script>", inline_script_start)
    callback_index = text.find("window.initAiItineraryMap = function initAiItineraryMap()")

    assert inline_script_start != -1
    assert inline_script_end != -1
    assert callback_index != -1
    assert callback_index < maps_script_tag_open_index
    assert inline_script_end < maps_script_tag_open_index

    between = text[inline_script_end:maps_script_tag_open_index]
    assert "const reservationImageFileInput" not in between


def test_base_template_dynamic_cache_busting_versions(client):
    res = client.get("/login")
    assert res.status_code == 200
    import re
    css_match = re.search(r'href="/static/css/app\.css\?v=(\d+)"', res.text)
    js_match = re.search(r'src="/static/js/app\.js\?v=(\d+)"', res.text)
    assert css_match is not None, "app.css does not have dynamic cache busting timestamp"
    assert js_match is not None, "app.js does not have dynamic cache busting timestamp"
    from app.routers.pages import get_static_version
    assert css_match.group(1) == get_static_version("static/css/app.css")
    assert js_match.group(1) == get_static_version("static/js/app.js")
