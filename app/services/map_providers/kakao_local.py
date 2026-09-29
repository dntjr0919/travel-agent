from __future__ import annotations

from urllib.parse import quote

import httpx

from app.core.errors import AppError
from app.services.map_providers.base import PlaceSearchResult

KAKAO_KEYWORD_SEARCH_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"


def search_kakao_places(query: str, api_key: str) -> list[PlaceSearchResult]:
    """Kakao Local 키워드 검색으로 국내 장소를 검색한다."""
    if not api_key:
        raise AppError(
            503,
            "PLACE_SEARCH_NOT_CONFIGURED",
            "Kakao Local API 키가 설정되지 않았습니다.",
        )

    headers = {
        "Authorization": f"KakaoAK {api_key}",
    }

    params = {
        "query": query,
        "size": 10,
    }

    try:
        response = httpx.get(
            KAKAO_KEYWORD_SEARCH_URL,
            headers=headers,
            params=params,
            timeout=10.0,
        )
        response.raise_for_status()
    except httpx.TimeoutException:
        raise AppError(
            504,
            "PLACE_SEARCH_TIMEOUT",
            "Kakao 장소 검색 요청 시간이 초과되었습니다.",
        )
    except httpx.HTTPStatusError:
        raise AppError(
        502,
        "PLACE_SEARCH_PROVIDER_ERROR",
        "Kakao 장소 검색에 실패했습니다.",
    )
    except httpx.HTTPError as exc:
        raise AppError(
            502,
            "PLACE_SEARCH_PROVIDER_ERROR",
            "Kakao 장소 검색에 실패했습니다.",
        )

    documents = response.json().get("documents", [])

    results: list[PlaceSearchResult] = []

    for document in documents:
        place_name = document.get("place_name", "이름 없음")
        road_address = document.get("road_address_name")
        address = road_address or document.get("address_name")

        latitude = float(document["y"]) if document.get("y") else None
        longitude = float(document["x"]) if document.get("x") else None

        map_url = (
            f"https://map.kakao.com/link/map/"
            f"{quote(place_name)},{latitude},{longitude}"
            if latitude is not None and longitude is not None
            else None
        )

        results.append(
            PlaceSearchResult(
                provider="kakao",
                external_place_id=document["id"],
                name=place_name,
                address=address,
                latitude=latitude,
                longitude=longitude,
                category=document.get("category_group_name"),
                map_url=map_url,
                source_url=document.get("place_url"),
            )
        )

    return results