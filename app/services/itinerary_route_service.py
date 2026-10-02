from __future__ import annotations

import math
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.models.itinerary import ItineraryItem
from app.schemas.itinerary import (
    ItineraryRouteLegOut,
    ItineraryRouteRequest,
    ItineraryRouteResponse,
)
from app.services.map_providers.google_routes import compute_walking_leg
from app.services.permission_service import require_member, require_trip

ITINERARY_ROUTE_WARNING = "Google Routes API의 예상 도보 시간이며 실제 상황에 따라 달라질 수 있습니다."
MAX_ITINERARY_ROUTE_PLACES = 10


def _has_valid_coordinates(item: ItineraryItem) -> bool:
    latitude = item.latitude
    longitude = item.longitude
    return (
        isinstance(latitude, (int, float))
        and not isinstance(latitude, bool)
        and math.isfinite(latitude)
        and -90 <= latitude <= 90
        and isinstance(longitude, (int, float))
        and not isinstance(longitude, bool)
        and math.isfinite(longitude)
        and -180 <= longitude <= 180
    )


def calculate_itinerary_routes(
    db: Session,
    trip_id: int,
    user_id: int,
    request: ItineraryRouteRequest,
) -> ItineraryRouteResponse:
    trip = require_trip(db, trip_id)
    require_member(db, trip_id, user_id)

    if request.date < trip.start_date or request.date > trip.end_date:
        raise AppError(
            422,
            "ITINERARY_ROUTE_INVALID_DATE",
            "요청 날짜가 여행 기간을 벗어났습니다.",
        )

    try:
        timezone = ZoneInfo(trip.timezone)
    except Exception:
        timezone = ZoneInfo("UTC")

    items = db.scalars(
        select(ItineraryItem)
        .where(ItineraryItem.trip_id == trip_id)
        .order_by(ItineraryItem.start_at.asc().nulls_last(), ItineraryItem.id.asc())
    ).all()
    route_items = [
        item
        for item in items
        if item.start_at is not None
        and item.start_at.astimezone(timezone).date() == request.date
        and _has_valid_coordinates(item)
    ]

    if len(route_items) < 2:
        raise AppError(
            422,
            "ITINERARY_ROUTE_NOT_ENOUGH_PLACES",
            "지도 좌표가 있는 일정이 2개 이상 필요합니다.",
        )
    if len(route_items) > MAX_ITINERARY_ROUTE_PLACES:
        raise AppError(
            422,
            "ITINERARY_ROUTE_TOO_MANY_PLACES",
            "도보 동선 계산은 하루 최대 10개 일정까지 가능합니다.",
        )

    api_key = (get_settings().google_maps_api_key or "").strip()
    if not api_key:
        raise AppError(
            503,
            "ITINERARY_ROUTE_NOT_CONFIGURED",
            "Google Routes API 키가 설정되지 않았습니다.",
        )

    legs: list[ItineraryRouteLegOut] = []
    try:
        for origin, destination in zip(route_items, route_items[1:]):
            duration_seconds, distance_meters = compute_walking_leg(
                origin_latitude=origin.latitude,
                origin_longitude=origin.longitude,
                destination_latitude=destination.latitude,
                destination_longitude=destination.longitude,
                api_key=api_key,
            )
            legs.append(
                ItineraryRouteLegOut(
                    from_itinerary_id=origin.id,
                    to_itinerary_id=destination.id,
                    duration_seconds=duration_seconds,
                    distance_meters=distance_meters,
                )
            )
    except AppError as exc:
        if exc.code == "AI_ITINERARY_ROUTE_INVALID_RESPONSE":
            raise AppError(
                502,
                "ITINERARY_ROUTE_INVALID_RESPONSE",
                "도보 동선 계산 결과를 해석할 수 없습니다.",
            ) from exc
        raise AppError(
            502,
            "ITINERARY_ROUTE_PROVIDER_ERROR",
            "도보 동선 계산 중 외부 서비스 호출에 실패했습니다.",
        ) from exc
    except Exception as exc:
        raise AppError(
            502,
            "ITINERARY_ROUTE_PROVIDER_ERROR",
            "도보 동선 계산 중 외부 서비스 호출에 실패했습니다.",
        ) from exc

    return ItineraryRouteResponse(
        travel_mode="WALK",
        date=request.date,
        legs=legs,
        warnings=[ITINERARY_ROUTE_WARNING],
    )