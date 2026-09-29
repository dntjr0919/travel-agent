from __future__ import annotations

import httpx

from app.core.errors import AppError
from app.services.map_providers.base import PlaceSearchResult

GOOGLE_TEXT_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"

GOOGLE_FIELD_MASK = ",".join(
    [
        "places.id",
        "places.displayName",
        "places.formattedAddress",
        "places.location",
        "places.primaryType",
        "places.googleMapsUri",
    ]
)


def search_google_places(query: str, api_key: str) -> list[PlaceSearchResult]:
    """Google Places API (New) Text Search로 해외 장소를 검색한다."""
    if not api_key:
        raise AppError(
            503,
            "PLACE_SEARCH_NOT_CONFIGURED",
            "Google Places API 키가 설정되지 않았습니다.",
        )

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": GOOGLE_FIELD_MASK,
    }

    payload = {
        "textQuery": query,
        "languageCode": "ko",
        "maxResultCount": 10,
    }

    try:
        response = httpx.post(
            GOOGLE_TEXT_SEARCH_URL,
            headers=headers,
            json=payload,
            timeout=10.0,
        )
        response.raise_for_status()
    except httpx.TimeoutException:
        raise AppError(
            504,
            "PLACE_SEARCH_TIMEOUT",
            "Google 장소 검색 요청 시간이 초과되었습니다.",
        )
    except httpx.HTTPStatusError:
        raise AppError(
            502,
            "PLACE_SEARCH_PROVIDER_ERROR",
            "Google 장소 검색에 실패했습니다.",
        )
    except httpx.HTTPError:
        raise AppError(
            502,
            "PLACE_SEARCH_PROVIDER_ERROR",
            "Google 장소 검색에 실패했습니다.",
        )

    places = response.json().get("places", [])

    results: list[PlaceSearchResult] = []

    for place in places:
        location = place.get("location", {})
        display_name = place.get("displayName", {})

        results.append(
            PlaceSearchResult(
                provider="google",
                external_place_id=place["id"],
                name=display_name.get("text", "이름 없음"),
                address=place.get("formattedAddress"),
                latitude=location.get("latitude"),
                longitude=location.get("longitude"),
                category=place.get("primaryType"),
                map_url=place.get("googleMapsUri"),
            )
        )

    return results