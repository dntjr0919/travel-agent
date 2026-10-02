from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field
from pydantic import model_validator


class AiItineraryDraftCreate(BaseModel):
    style: str
    interests: list[str] = Field(default_factory=list)
    pace: str
    model: str | None = None


class AiItineraryDraftItemOut(BaseModel):
    provider: str
    external_place_id: str
    name: str
    address: str | None
    latitude: float | None
    longitude: float | None
    category: str | None
    map_url: str | None
    source_url: str | None
    reason: str
    suggested_stay_minutes: int


class AiItineraryDraftDayOut(BaseModel):
    date: date
    items: list[AiItineraryDraftItemOut]


class AiItineraryDraftOut(BaseModel):
    destination: str
    start_date: date
    end_date: date
    days: list[AiItineraryDraftDayOut]
    warnings: list[str]


class AiItinerarySearchPlanQuery(BaseModel):
    query: str = Field(min_length=1, max_length=120)
    category: str = Field(min_length=1, max_length=30)


class AiItinerarySearchPlanResponse(BaseModel):
    queries: list[AiItinerarySearchPlanQuery]


class AiItineraryCourseItem(BaseModel):
    external_place_id: str = Field(min_length=1, max_length=255)
    reason: str = Field(min_length=1, max_length=300)
    suggested_stay_minutes: int


class AiItineraryCourseDay(BaseModel):
    date: date
    items: list[AiItineraryCourseItem]


class AiItineraryCourseResponse(BaseModel):
    days: list[AiItineraryCourseDay]
    warnings: list[str] = Field(default_factory=list)


class AiItineraryRoutePlaceIn(BaseModel):
    external_place_id: str = Field(min_length=1, max_length=255)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class AiItineraryRouteDayIn(BaseModel):
    date: date
    places: list[AiItineraryRoutePlaceIn] = Field(min_length=2)

    @model_validator(mode="after")
    def check_duplicate_place_ids(self) -> "AiItineraryRouteDayIn":
        seen: set[str] = set()
        for place in self.places:
            place_id = place.external_place_id.strip()
            if place_id in seen:
                raise ValueError("DUPLICATE_PLACE_ID")
            seen.add(place_id)
        return self


class AiItineraryRouteRequest(BaseModel):
    days: list[AiItineraryRouteDayIn] = Field(min_length=1, max_length=31)

    @model_validator(mode="after")
    def check_absolute_total_places_limit(self) -> "AiItineraryRouteRequest":
        # Anti-abuse upper bound; actual trip-based limits are validated in service.
        total_places = sum(len(day.places) for day in self.days)
        if total_places > 124:
            raise ValueError("TOO_MANY_PLACES_ABSOLUTE")
        return self


class AiItineraryRouteLegOut(BaseModel):
    from_external_place_id: str
    to_external_place_id: str
    duration_seconds: int
    distance_meters: int


class AiItineraryRouteDayOut(BaseModel):
    date: date
    legs: list[AiItineraryRouteLegOut]


class AiItineraryRouteResponse(BaseModel):
    travel_mode: str = "WALK"
    days: list[AiItineraryRouteDayOut]
    warnings: list[str]
