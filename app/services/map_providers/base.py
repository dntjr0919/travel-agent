from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PlaceSearchResult:
    provider: str
    external_place_id: str
    name: str
    address: str | None
    latitude: float | None
    longitude: float | None
    category: str | None
    map_url: str | None
    source_url: str | None = None