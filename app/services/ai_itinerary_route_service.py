from __future__ import annotations

from datetime import date, timedelta

from app.core.config import get_settings
from app.core.errors import AppError
from app.schemas.ai_itinerary import (
    AiItineraryRouteDayIn,
    AiItineraryRouteDayOut,
    AiItineraryRouteLegOut,
    AiItineraryRouteRequest,
    AiItineraryRouteResponse,
)
from app.services.map_providers.google_routes import compute_walking_leg

AI_ROUTE_WARNING = "도보 이동 시간과 거리는 Google Routes API 계산 시점의 추정치입니다."


def _travel_dates(start_date: date, end_date: date) -> set[date]:
    dates: set[date] = set()
    cursor = start_date
    while cursor <= end_date:
        dates.add(cursor)
        cursor += timedelta(days=1)
    return dates


def _validate_request_against_trip(
    request: AiItineraryRouteRequest,
    start_date: date,
    end_date: date,
) -> None:
    trip_dates = _travel_dates(start_date, end_date)
    trip_day_count = (end_date - start_date).days + 1
    max_total_places = trip_day_count * 4

    if len(request.days) > trip_day_count:
        raise AppError(
            422,
            "AI_ITINERARY_ROUTE_TOO_MANY_PLACES",
            "하루 장소 수 또는 전체 장소 수 제한을 초과했습니다.",
        )

    total_places = 0
    seen_dates: set[date] = set()

    for day in request.days:
        if day.date in seen_dates:
            raise AppError(
                422,
                "AI_ITINERARY_ROUTE_INVALID_DATE",
                "요청에 중복된 날짜가 포함되어 있습니다.",
            )
        seen_dates.add(day.date)

        if day.date not in trip_dates:
            raise AppError(
                422,
                "AI_ITINERARY_ROUTE_INVALID_DATE",
                "여행 기간을 벗어난 날짜가 포함되어 있습니다.",
            )

        if len(day.places) > 4:
            raise AppError(
                422,
                "AI_ITINERARY_ROUTE_TOO_MANY_PLACES",
                "하루 장소 수 또는 전체 장소 수 제한을 초과했습니다.",
            )

        total_places += len(day.places)

    if total_places > max_total_places:
        raise AppError(
            422,
            "AI_ITINERARY_ROUTE_TOO_MANY_PLACES",
            "하루 장소 수 또는 전체 장소 수 제한을 초과했습니다.",
        )


def _compute_day_legs(day: AiItineraryRouteDayIn, api_key: str) -> list[AiItineraryRouteLegOut]:
    legs: list[AiItineraryRouteLegOut] = []

    for idx in range(len(day.places) - 1):
        origin = day.places[idx]
        destination = day.places[idx + 1]

        duration_seconds, distance_meters = compute_walking_leg(
            origin_latitude=origin.latitude,
            origin_longitude=origin.longitude,
            destination_latitude=destination.latitude,
            destination_longitude=destination.longitude,
            api_key=api_key,
        )

        legs.append(
            AiItineraryRouteLegOut(
                from_external_place_id=origin.external_place_id,
                to_external_place_id=destination.external_place_id,
                duration_seconds=duration_seconds,
                distance_meters=distance_meters,
            )
        )

    return legs


def calculate_ai_itinerary_routes(
    *,
    request: AiItineraryRouteRequest,
    trip_start_date: date,
    trip_end_date: date,
) -> AiItineraryRouteResponse:
    _validate_request_against_trip(request, trip_start_date, trip_end_date)

    settings = get_settings()
    api_key = (settings.google_maps_api_key or "").strip()
    if not api_key:
        raise AppError(
            503,
            "AI_ITINERARY_ROUTE_NOT_CONFIGURED",
            "Google Routes API 키가 설정되지 않았습니다.",
        )

    day_out_list: list[AiItineraryRouteDayOut] = []

    for day in request.days:
        try:
            legs = _compute_day_legs(day, api_key)
        except AppError as exc:
            if exc.code == "AI_ITINERARY_ROUTE_INVALID_RESPONSE":
                raise
            raise AppError(
                502,
                "AI_ITINERARY_ROUTE_PROVIDER_ERROR",
                "도보 동선 계산 중 외부 서비스 호출에 실패했습니다.",
            ) from exc
        except Exception as exc:
            raise AppError(
                502,
                "AI_ITINERARY_ROUTE_PROVIDER_ERROR",
                "도보 동선 계산 중 외부 서비스 호출에 실패했습니다.",
            ) from exc

        day_out_list.append(AiItineraryRouteDayOut(date=day.date, legs=legs))

    return AiItineraryRouteResponse(
        travel_mode="WALK",
        days=day_out_list,
        warnings=[AI_ROUTE_WARNING],
    )
