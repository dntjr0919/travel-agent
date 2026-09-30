from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator
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

    @model_validator(mode="after")
    def check_time_range(self) -> "ItineraryCreate":
        if self.start_at and self.end_at and self.start_at > self.end_at:
            raise ValueError("INVALID_TIME_RANGE")
        return self


class ItineraryUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    category: str | None = Field(default=None, pattern=CATEGORY_PATTERN)
    status: ItineraryStatus | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    location_name: str | None = Field(default=None, max_length=200)
    memo: str | None = None
    version: int = Field(ge=1)

    @model_validator(mode="after")
    def check_time_range(self) -> "ItineraryUpdate":
        if self.start_at and self.end_at and self.start_at > self.end_at:
            raise ValueError("INVALID_TIME_RANGE")
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
    created_by: int
    updated_by: int
    created_by_name: str
    updated_by_name: str
    version: int
    created_at: datetime
    updated_at: datetime
