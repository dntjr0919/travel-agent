from __future__ import annotations

from pydantic import BaseModel, Field, StrictInt

from app.schemas.itinerary import ItineraryOut


class ExternalLlmItineraryAnalyzeRequest(BaseModel):
    raw_json: str


class ExternalLlmItineraryImportRequest(BaseModel):
    raw_json: str
    selected_indices: list[StrictInt] = Field(min_length=1, max_length=30)


class ExternalLlmItineraryItemAnalysis(BaseModel):
    index: int
    date: str | None
    title: str
    valid: bool
    error: str | None = None
    warning: str | None = None


class ExternalLlmItineraryAnalyzeResponse(BaseModel):
    items: list[ExternalLlmItineraryItemAnalysis]


class ExternalLlmItineraryImportResponse(BaseModel):
    created_count: int
    items: list[ItineraryOut]