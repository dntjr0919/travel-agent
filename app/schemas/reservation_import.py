from __future__ import annotations

from datetime import datetime
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator, model_validator

DEFAULT_WARNING = "AI가 추출한 초안입니다. 원본 예약 정보와 대조한 뒤 저장하세요."


class ReservationImportAnalyzeOut(BaseModel):
    kind: str = Field(pattern="^(transport|accommodation)$")
    transport_mode: str | None = Field(default=None, pattern="^(flight|train|intercity_bus)$")
    title: str = Field(min_length=1, max_length=200)
    provider_name: str | None = Field(default=None, max_length=120)
    service_number: str | None = Field(default=None, max_length=80)
    departure_name: str | None = Field(default=None, max_length=200)
    arrival_name: str | None = Field(default=None, max_length=200)
    departure_at: datetime | None = None
    arrival_at: datetime | None = None
    accommodation_name: str | None = Field(default=None, max_length=200)
    checkin_at: datetime | None = None
    checkout_at: datetime | None = None
    price_amount: float | None = None
    currency: str | None = Field(default=None, max_length=12)
    booking_url: str | None = None
    memo: str | None = None
    warnings: list[str] = Field(default_factory=lambda: [DEFAULT_WARNING])

    @field_validator("booking_url")
    @classmethod
    def validate_booking_url(cls, value: str | None) -> str | None:
        if value is None:
            return None

        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("INVALID_BOOKING_URL")
        return value

    @field_validator("departure_at", "arrival_at", "checkin_at", "checkout_at")
    @classmethod
    def validate_timezone_aware_datetimes(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("DATETIME_TZ_REQUIRED")
        return value

    @field_validator("warnings")
    @classmethod
    def validate_warnings(cls, value: list[str]) -> list[str]:
        normalized = [warning.strip() for warning in value if warning and warning.strip()]
        if not normalized:
            return [DEFAULT_WARNING]
        return normalized

    @model_validator(mode="after")
    def validate_kind_specific_fields(self) -> "ReservationImportAnalyzeOut":
        
        if self.kind == "accommodation":
            self.transport_mode = None

        return self
