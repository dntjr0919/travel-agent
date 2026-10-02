from __future__ import annotations

import httpx

from app.core.errors import AppError

GOOGLE_COMPUTE_ROUTES_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"
GOOGLE_ROUTES_FIELD_MASK = "routes.duration,routes.distanceMeters"


def _parse_duration_seconds(value: str) -> int:
    if not value or not value.endswith("s"):
        raise AppError(
            502,
            "AI_ITINERARY_ROUTE_INVALID_RESPONSE",
            "도보 동선 계산 결과를 해석할 수 없습니다.",
        )

    number_text = value[:-1].strip()
    try:
        seconds = float(number_text)
    except ValueError as exc:
        raise AppError(
            502,
            "AI_ITINERARY_ROUTE_INVALID_RESPONSE",
            "도보 동선 계산 결과를 해석할 수 없습니다.",
        ) from exc

    if seconds < 0:
        raise AppError(
            502,
            "AI_ITINERARY_ROUTE_INVALID_RESPONSE",
            "도보 동선 계산 결과를 해석할 수 없습니다.",
        )

    return int(round(seconds))


def compute_walking_leg(
    origin_latitude: float,
    origin_longitude: float,
    destination_latitude: float,
    destination_longitude: float,
    api_key: str,
) -> tuple[int, int]:
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": GOOGLE_ROUTES_FIELD_MASK,
    }
    payload = {
        "origin": {
            "location": {
                "latLng": {
                    "latitude": origin_latitude,
                    "longitude": origin_longitude,
                }
            }
        },
        "destination": {
            "location": {
                "latLng": {
                    "latitude": destination_latitude,
                    "longitude": destination_longitude,
                }
            }
        },
        "intermediates": [],
        "travelMode": "WALK",
        "optimizeWaypointOrder": False,
    }

    try:
        response = httpx.post(
            GOOGLE_COMPUTE_ROUTES_URL,
            headers=headers,
            json=payload,
            timeout=8.0,
        )
        response.raise_for_status()
    except httpx.TimeoutException as exc:
        raise AppError(
            502,
            "AI_ITINERARY_ROUTE_PROVIDER_ERROR",
            "도보 동선 계산 중 외부 서비스 호출에 실패했습니다.",
        ) from exc
    except httpx.HTTPStatusError as exc:
        raise AppError(
            502,
            "AI_ITINERARY_ROUTE_PROVIDER_ERROR",
            "도보 동선 계산 중 외부 서비스 호출에 실패했습니다.",
        ) from exc
    except httpx.HTTPError as exc:
        raise AppError(
            502,
            "AI_ITINERARY_ROUTE_PROVIDER_ERROR",
            "도보 동선 계산 중 외부 서비스 호출에 실패했습니다.",
        ) from exc

    body = response.json()
    routes = body.get("routes")

    if not isinstance(routes, list) or not routes:
        raise AppError(
            502,
            "AI_ITINERARY_ROUTE_INVALID_RESPONSE",
            "도보 동선 계산 결과를 해석할 수 없습니다.",
        )

    first_route = routes[0]
    if not isinstance(first_route, dict):
        raise AppError(
            502,
            "AI_ITINERARY_ROUTE_INVALID_RESPONSE",
            "도보 동선 계산 결과를 해석할 수 없습니다.",
        )

    duration_value = first_route.get("duration")
    distance_value = first_route.get("distanceMeters")

    if not isinstance(duration_value, str):
        raise AppError(
            502,
            "AI_ITINERARY_ROUTE_INVALID_RESPONSE",
            "도보 동선 계산 결과를 해석할 수 없습니다.",
        )

    if not isinstance(distance_value, int) or distance_value < 0:
        raise AppError(
            502,
            "AI_ITINERARY_ROUTE_INVALID_RESPONSE",
            "도보 동선 계산 결과를 해석할 수 없습니다.",
        )

    duration_seconds = _parse_duration_seconds(duration_value)
    return duration_seconds, distance_value
