from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from app.models.itinerary import ItineraryStatus

CATEGORY_PATTERN = "^(transportation|accommodation|sightseeing|food|shopping|other)$"


class ItineraryCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    status: ItineraryStatus = Field(default=ItineraryStatus.PLANNED)
    category: str = Field(default="other", pattern=CATEGORY_PATTERN)
    start_at: datetime | None = None
    end_at: datetime | None = None
    location_name: str | None = Field(default=None, max_length=200)
    memo: str | None = None
    place_candidate_id: int | None = Field(default=None, ge=1)
    place_provider: Literal["google", "kakao"] | None = None
    external_place_id: str | None = Field(default=None, max_length=255)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)

    @field_validator("external_place_id")
    @classmethod
    def normalize_external_place_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @model_validator(mode="after")
    def check_time_range(self) -> "ItineraryCreate":
        if self.start_at and self.end_at and self.start_at > self.end_at:
            raise ValueError("INVALID_TIME_RANGE")
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("INVALID_COORDINATE_PAIR")
        return self


class ItineraryUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    category: str | None = Field(default=None, pattern=CATEGORY_PATTERN)
    status: ItineraryStatus | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    location_name: str | None = Field(default=None, max_length=200)
    memo: str | None = None
    place_candidate_id: int | None = Field(default=None, ge=1)
    place_provider: Literal["google", "kakao"] | None = None
    external_place_id: str | None = Field(default=None, max_length=255)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    version: int = Field(ge=1)

    @field_validator("external_place_id")
    @classmethod
    def normalize_external_place_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @model_validator(mode="after")
    def check_time_range(self) -> "ItineraryUpdate":
        if self.start_at and self.end_at and self.start_at > self.end_at:
            raise ValueError("INVALID_TIME_RANGE")

        has_lat_field = "latitude" in self.model_fields_set
        has_lng_field = "longitude" in self.model_fields_set
        if has_lat_field != has_lng_field:
            raise ValueError("INVALID_COORDINATE_PAIR")

        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("INVALID_COORDINATE_PAIR")

        return self


class ItineraryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    trip_id: int
    title: str
    category: str
    status: str
    start_at: datetime | None
    end_at: datetime | None
    location_name: str | None
    memo: str | None
    place_candidate_id: int | None
    place_provider: str | None
    external_place_id: str | None
    latitude: float | None
    longitude: float | None
    created_by: int
    updated_by: int
    created_by_name: str
    updated_by_name: str
    version: int
    created_at: datetime
    updated_at: datetime
