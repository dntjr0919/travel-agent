from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


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
