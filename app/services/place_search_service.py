from __future__ import annotations

from app.core.config import get_settings
from app.core.errors import AppError
from app.services.map_providers.base import PlaceSearchResult
from app.services.map_providers.google_places import search_google_places
from app.services.map_providers.kakao_local import search_kakao_places

settings = get_settings()


def search_places(scope: str, query: str) -> tuple[str, list[PlaceSearchResult]]:
    """검색 범위에 따라 Google 또는 Kakao 장소 검색 공급자를 선택한다."""
    normalized_query = query.strip()

    if len(normalized_query) < 2:
        raise AppError(
            422,
            "PLACE_SEARCH_QUERY_TOO_SHORT",
            "장소 검색어는 2글자 이상 입력하세요.",
        )

    if scope == "international":
        results = search_google_places(
            normalized_query,
            settings.google_maps_api_key,
        )
        return "google", results

    if scope == "domestic":
        results = search_kakao_places(
            normalized_query,
            settings.kakao_rest_api_key,
        )
        return "kakao", results

    raise AppError(
        422,
        "INVALID_PLACE_SEARCH_SCOPE",
        "검색 범위는 domestic 또는 international이어야 합니다.",
    )