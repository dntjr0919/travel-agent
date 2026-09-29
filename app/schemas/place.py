from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl
from typing import Literal


class PlaceCandidateCreate(BaseModel):
    provider: str = Field(min_length=1, max_length=30)
    external_place_id: str = Field(min_length=1, max_length=255)
    name: str = Field(min_length=1, max_length=200)
    address: str | None = Field(default=None, max_length=500)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    category: str | None = Field(default=None, max_length=100)
    map_url: HttpUrl | None = None
    source_url: HttpUrl | None = None
    memo: str | None = None


class PlaceCandidateUpdate(BaseModel):
    memo: str | None = None


class PlaceCandidateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    trip_id: int
    provider: str
    external_place_id: str
    name: str
    address: str | None
    latitude: float | None
    longitude: float | None
    category: str | None
    map_url: str | None
    source_url: str | None
    memo: str | None
    created_by: int
    created_by_name: str
    created_at: datetime
    updated_at: datetime

class PlaceSearchOut(BaseModel):
    provider: str
    external_place_id: str
    name: str
    address: str | None
    latitude: float | None
    longitude: float | None
    category: str | None
    map_url: str | None
    source_url: str | None = None


class PlaceSearchResponse(BaseModel):
    provider: str
    query: str
    results: list[PlaceSearchOut]