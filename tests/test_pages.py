from __future__ import annotations

from app.core.config import get_settings
from tests.conftest import register_and_login
from tests.test_trips import create_trip


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
    assert 'id="trip-mobile-tabs"' in text
    assert 'id="trip-mobile-tab-schedule"' in text
    assert 'id="trip-mobile-tab-map"' in text
    assert 'id="item-form-cancel"' in text
    assert 'id="trip-edit-cancel"' in text
    assert 'id="item-place-search-toggle-btn"' in text
    assert 'id="item-place-search-panel"' in text
    assert 'id="item-place-search-query"' in text
    assert 'id="item-place-search-results"' in text
    assert 'id="ai-itinerary-map"' not in text
    assert 'id="saved-candidates-map"' not in text


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
