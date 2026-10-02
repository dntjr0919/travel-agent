from __future__ import annotations

import json
import logging
import math
from datetime import date, timedelta

from app.core.config import DEFAULT_RESERVATION_ANALYSIS_MODEL, RESERVATION_ANALYSIS_MODEL_NAMES
from app.core.errors import AppError
from app.schemas.ai_itinerary import (
    AiItineraryCourseResponse,
    AiItineraryDraftDayOut,
    AiItineraryDraftItemOut,
    AiItineraryDraftOut,
    AiItinerarySearchPlanResponse,
)
from app.services.llm.gemini_provider import get_gemini_text_json
from app.services.map_providers.base import PlaceSearchResult
from app.services.place_search_service import search_places

logger = logging.getLogger(__name__)

AI_ITINERARY_DEFAULT_WARNING = "AI가 구성한 초안입니다. 영업시간, 휴무일, 입장 조건은 방문 전에 원본 정보와 대조하세요."
ALLOWED_INTERESTS = {"culture", "cafe", "nature", "shopping", "food", "night_view"}
ALLOWED_PACES = {"relaxed", "balanced", "packed"}
AI_ITINERARY_LOCATION_BIAS_RADIUS_METERS = 30000.0


def _strip_markdown_code_fence(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if len(lines) >= 2 and lines[-1].strip() == "```":
            cleaned = "\n".join(lines[1:-1]).strip()
        elif len(lines) >= 1:
            cleaned = "\n".join(lines[1:]).strip()
    return cleaned


def resolve_ai_itinerary_model(model: str | None) -> str:
    model_key = (model or "").strip() or DEFAULT_RESERVATION_ANALYSIS_MODEL
    model_name = RESERVATION_ANALYSIS_MODEL_NAMES.get(model_key)
    if not model_name:
        raise AppError(422, "AI_ITINERARY_INVALID_MODEL", "지원하지 않는 분석 모델입니다.")
    return model_name


def _validate_style(style: str) -> str:
    normalized = style.strip()
    if len(normalized) < 2:
        raise AppError(422, "AI_ITINERARY_STYLE_TOO_SHORT", "여행 스타일은 2자 이상 입력하세요.")
    if len(normalized) > 300:
        raise AppError(422, "AI_ITINERARY_STYLE_TOO_LONG", "여행 스타일은 300자 이내로 입력하세요.")
    return normalized


def _validate_interests(interests: list[str]) -> list[str]:
    if len(interests) > 6:
        raise AppError(422, "AI_ITINERARY_INVALID_INTEREST", "관심사는 최대 6개까지 선택할 수 있습니다.")

    normalized: list[str] = []
    for interest in interests:
        value = (interest or "").strip()
        if value not in ALLOWED_INTERESTS:
            raise AppError(422, "AI_ITINERARY_INVALID_INTEREST", "지원하지 않는 관심사입니다.")
        if value not in normalized:
            normalized.append(value)

    return normalized


def _validate_pace(pace: str) -> str:
    normalized = (pace or "").strip()
    if normalized not in ALLOWED_PACES:
        raise AppError(422, "AI_ITINERARY_INVALID_PACE", "이동 강도 값이 올바르지 않습니다.")
    return normalized


def _build_travel_dates(start_date: date, end_date: date) -> list[date]:
    days: list[date] = []
    cursor = start_date
    while cursor <= end_date:
        days.append(cursor)
        cursor += timedelta(days=1)
    return days


def _load_json_object(text: str, *, code: str, detail: str) -> dict:
    cleaned = _strip_markdown_code_fence(text)
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError:
        raise AppError(502, code, detail)

    if not isinstance(payload, dict):
        raise AppError(502, code, detail)

    return payload


def _build_search_plan_prompt(
    *,
    destination: str,
    start_date: date,
    end_date: date,
    style: str,
    interests: list[str],
    pace: str,
) -> str:
    interests_text = ", ".join(interests) if interests else "none"
    return f"""
당신은 해외 여행 장소 탐색 도우미입니다.
아래 입력을 바탕으로 Google Places Text Search용 검색어 계획 JSON만 반환하세요.

입력:
- destination: {destination}
- start_date: {start_date.isoformat()}
- end_date: {end_date.isoformat()}
- style: {style}
- interests: {interests_text}
- pace: {pace}

반환 형식(JSON object):
{{
  "queries": [
    {{"query": "destination 포함 자연어 검색어", "category": "culture|cafe|nature|shopping|food|night_view"}}
  ]
}}

규칙:
- queries 길이는 1~4
- 검색어는 여행 목적지를 명확히 포함한 Google Places Text Search용 쿼리여야 함
- 다른 국가나 도시 장소를 추천하거나 검색하지 말 것
- query는 Google Places Text Search에 적합한 자연어 문장
- 장소명, 주소, 좌표, 가격, 일정, 허구 장소를 반환하지 말 것
- JSON 외 텍스트 금지
""".strip()


def _build_course_prompt(
    *,
    destination: str,
    start_date: date,
    end_date: date,
    style: str,
    interests: list[str],
    pace: str,
    candidates: list[dict],
) -> str:
    interests_text = ", ".join(interests) if interests else "none"
    candidates_json = json.dumps(candidates, ensure_ascii=False)
    return f"""
당신은 해외 여행 코스 플래너입니다.
입력된 실제 장소 후보 목록에서만 선택해 날짜별 코스 초안을 JSON으로 반환하세요.

입력:
- destination: {destination}
- start_date: {start_date.isoformat()}
- end_date: {end_date.isoformat()}
- style: {style}
- interests: {interests_text}
- pace: {pace}
- candidates: {candidates_json}

반환 형식(JSON object):
{{
  "days": [
    {{
      "date": "YYYY-MM-DD",
      "items": [
        {{
          "external_place_id": "candidates에 있는 ID",
          "reason": "추천 이유",
          "suggested_stay_minutes": 120
        }}
      ]
    }}
  ],
  "warnings": ["주의 문구"]
}}

규칙:
- candidates 목록에 있는 external_place_id만 선택
- 새 장소명, 주소, 좌표, ID 생성 금지
- 여행 기간 안의 YYYY-MM-DD 날짜만 사용
- 하루 1~4개 장소
- suggested_stay_minutes는 30~360 정수, 30분 단위
- 모든 장소를 반드시 사용할 필요 없음
- JSON 외 텍스트 금지
""".strip()


def _normalize_place_search_error(exc: AppError) -> AppError:
    if exc.code == "PLACE_SEARCH_NOT_CONFIGURED":
        return AppError(503, "AI_ITINERARY_PROVIDER_ERROR", "AI 코스 생성을 위한 Google Places 설정이 필요합니다.")
    if exc.code in {"PLACE_SEARCH_TIMEOUT", "PLACE_SEARCH_PROVIDER_ERROR"}:
        return AppError(502, "AI_ITINERARY_PROVIDER_ERROR", "AI 코스 생성을 위한 Google Places 호출에 실패했습니다.")
    return exc


def _haversine_distance_meters(
    latitude1: float,
    longitude1: float,
    latitude2: float,
    longitude2: float,
) -> float:
    earth_radius_meters = 6371000.0

    lat1_rad = math.radians(latitude1)
    lon1_rad = math.radians(longitude1)
    lat2_rad = math.radians(latitude2)
    lon2_rad = math.radians(longitude2)

    lat_delta = lat2_rad - lat1_rad
    lon_delta = lon2_rad - lon1_rad

    a = (
        math.sin(lat_delta / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(lon_delta / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return earth_radius_meters * c


def _ensure_query_contains_destination(intent_query: str, destination: str) -> str:
    query = intent_query.strip()
    if not query:
        raise AppError(502, "AI_ITINERARY_INVALID_SEARCH_PLAN", "AI 검색 계획 결과를 해석할 수 없습니다.")

    normalized_destination = destination.strip()
    if not normalized_destination:
        raise AppError(422, "AI_ITINERARY_DESTINATION_REQUIRED", "여행지(destination)를 먼저 입력하세요.")

    if normalized_destination.lower() in query.lower():
        return query

    return f"{query}, {normalized_destination}"


def _resolve_destination_center(destination: str) -> tuple[float, float]:
    try:
        _, results = search_places("international", destination)
    except AppError as exc:
        raise _normalize_place_search_error(exc) from exc

    for place in results:
        if place.latitude is None or place.longitude is None:
            continue
        return float(place.latitude), float(place.longitude)

    raise AppError(422, "AI_ITINERARY_DESTINATION_NOT_FOUND", "여행 목적지의 위치를 찾을 수 없습니다.")


def _collect_candidates(
    queries: list[str],
    *,
    destination_center: tuple[float, float],
) -> list[PlaceSearchResult]:
    deduped: dict[str, PlaceSearchResult] = {}
    center_latitude, center_longitude = destination_center

    for query in queries:
        try:
            _, results = search_places(
                "international",
                query,
                location_bias=(
                    center_latitude,
                    center_longitude,
                    AI_ITINERARY_LOCATION_BIAS_RADIUS_METERS,
                ),
            )
        except AppError as exc:
            raise _normalize_place_search_error(exc) from exc

        for place in results[:5]:
            place_id = (place.external_place_id or "").strip()
            place_name = (place.name or "").strip()

            if not place_id or not place_name:
                continue

            if place.latitude is None or place.longitude is None:
                continue

            distance_meters = _haversine_distance_meters(
                center_latitude,
                center_longitude,
                float(place.latitude),
                float(place.longitude),
            )

            if distance_meters > AI_ITINERARY_LOCATION_BIAS_RADIUS_METERS:
                continue

            if place_id in deduped:
                continue

            deduped[place_id] = place

            if len(deduped) >= 20:
                break

        if len(deduped) >= 20:
            break

    return list(deduped.values())


def _normalize_warnings(raw_warnings: list[str] | None) -> list[str]:
    if not raw_warnings:
        return [AI_ITINERARY_DEFAULT_WARNING]

    normalized: list[str] = []
    for warning in raw_warnings:
        value = (warning or "").strip()
        if not value:
            continue
        if value not in normalized:
            normalized.append(value)

    if not normalized:
        normalized = [AI_ITINERARY_DEFAULT_WARNING]
    elif AI_ITINERARY_DEFAULT_WARNING not in normalized:
        normalized.append(AI_ITINERARY_DEFAULT_WARNING)

    return normalized


def create_ai_itinerary_draft(
    *,
    destination: str,
    start_date: date,
    end_date: date,
    timezone: str,
    style: str,
    interests: list[str],
    pace: str,
    model: str | None,
) -> AiItineraryDraftOut:
    normalized_destination = (destination or "").strip()
    if not normalized_destination:
        raise AppError(422, "AI_ITINERARY_DESTINATION_REQUIRED", "여행지(destination)를 먼저 입력하세요.")

    normalized_style = _validate_style(style)
    normalized_interests = _validate_interests(interests)
    normalized_pace = _validate_pace(pace)
    model_name = resolve_ai_itinerary_model(model)

    search_plan_prompt = _build_search_plan_prompt(
        destination=normalized_destination,
        start_date=start_date,
        end_date=end_date,
        style=normalized_style,
        interests=normalized_interests,
        pace=normalized_pace,
    )

    search_plan_text = get_gemini_text_json(prompt=search_plan_prompt, model_name=model_name)
    search_plan_payload = _load_json_object(
        search_plan_text,
        code="AI_ITINERARY_INVALID_SEARCH_PLAN",
        detail="AI 검색 계획 결과를 해석할 수 없습니다.",
    )

    try:
        search_plan = AiItinerarySearchPlanResponse.model_validate(search_plan_payload)
    except Exception:
        raise AppError(502, "AI_ITINERARY_INVALID_SEARCH_PLAN", "AI 검색 계획 결과를 해석할 수 없습니다.")

    if not (1 <= len(search_plan.queries) <= 4):
        raise AppError(502, "AI_ITINERARY_INVALID_SEARCH_PLAN", "AI 검색 계획 결과를 해석할 수 없습니다.")

    destination_lower = normalized_destination.lower()
    query_strings: list[str] = []

    for planned in search_plan.queries:
        query = planned.query.strip()
        if not query:
            raise AppError(502, "AI_ITINERARY_INVALID_SEARCH_PLAN", "AI 검색 계획 결과를 해석할 수 없습니다.")

        query_strings.append(_ensure_query_contains_destination(query, normalized_destination))

    destination_center = _resolve_destination_center(normalized_destination)

    candidates = _collect_candidates(query_strings, destination_center=destination_center)

    if not candidates:
        raise AppError(422, "AI_ITINERARY_NO_PLACE_CANDIDATES", "검색된 실제 장소 후보가 없습니다.")

    candidates_by_id = {
        place.external_place_id: place
        for place in candidates
        if (place.external_place_id or "").strip() and (place.name or "").strip()
    }

    llm_candidates = [
        {
            "external_place_id": place.external_place_id,
            "name": place.name,
            "address": place.address,
            "latitude": place.latitude,
            "longitude": place.longitude,
            "category": place.category,
        }
        for place in candidates_by_id.values()
    ]

    course_prompt = _build_course_prompt(
        destination=normalized_destination,
        start_date=start_date,
        end_date=end_date,
        style=normalized_style,
        interests=normalized_interests,
        pace=normalized_pace,
        candidates=llm_candidates,
    )

    course_text = get_gemini_text_json(prompt=course_prompt, model_name=model_name)
    course_payload = _load_json_object(
        course_text,
        code="AI_ITINERARY_INVALID_COURSE_RESPONSE",
        detail="AI 코스 구성 결과를 해석할 수 없습니다.",
    )

    try:
        course = AiItineraryCourseResponse.model_validate(course_payload)
    except Exception:
        raise AppError(502, "AI_ITINERARY_INVALID_COURSE_RESPONSE", "AI 코스 구성 결과를 해석할 수 없습니다.")

    travel_dates = _build_travel_dates(start_date, end_date)
    travel_date_set = {d.isoformat() for d in travel_dates}

    day_items_map: dict[str, list[AiItineraryDraftItemOut]] = {}
    used_place_ids_global: set[str] = set()

    for day in course.days:
        day_key = day.date.isoformat()
        if day_key not in travel_date_set:
            continue

        if day_key not in day_items_map:
            day_items_map[day_key] = []

        seen_in_day = {item.external_place_id for item in day_items_map[day_key]}

        for item in day.items:
            if len(day_items_map[day_key]) >= 4:
                break

            place_id = item.external_place_id.strip()
            if not place_id:
                continue
            if place_id in seen_in_day or place_id in used_place_ids_global:
                continue

            place = candidates_by_id.get(place_id)
            if place is None:
                continue

            reason = item.reason.strip()
            stay = item.suggested_stay_minutes

            if not reason or len(reason) > 300:
                continue
            if stay < 30 or stay > 360 or stay % 30 != 0:
                continue

            day_items_map[day_key].append(
                AiItineraryDraftItemOut(
                    provider=place.provider,
                    external_place_id=place.external_place_id,
                    name=place.name,
                    address=place.address,
                    latitude=place.latitude,
                    longitude=place.longitude,
                    category=place.category,
                    map_url=place.map_url,
                    source_url=place.source_url,
                    reason=reason,
                    suggested_stay_minutes=stay,
                )
            )
            seen_in_day.add(place_id)
            used_place_ids_global.add(place_id)

    total_valid_items = sum(len(items) for items in day_items_map.values())
    if total_valid_items == 0:
        logger.warning("ai itinerary invalid: no valid course items")
        raise AppError(502, "AI_ITINERARY_INVALID_COURSE_RESPONSE", "AI 코스 구성 결과를 해석할 수 없습니다.")

    output_days: list[AiItineraryDraftDayOut] = []
    for travel_date in travel_dates:
        day_key = travel_date.isoformat()
        output_days.append(
            AiItineraryDraftDayOut(
                date=travel_date,
                items=day_items_map.get(day_key, []),
            )
        )

    warnings = _normalize_warnings(course.warnings)

    return AiItineraryDraftOut(
        destination=normalized_destination,
        start_date=start_date,
        end_date=end_date,
        days=output_days,
        warnings=warnings,
    )
