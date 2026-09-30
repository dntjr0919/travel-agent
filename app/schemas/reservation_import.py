from __future__ import annotations

from datetime import datetime
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field, ValidationInfo, field_validator, model_validator

DEFAULT_WARNING = "AI가 추출한 초안입니다. 원본 예약 정보와 대조한 뒤 저장하세요."
TIMEZONE_FALLBACK_WARNING = "시간대 정보가 이미지에 없어 Asia/Seoul 기준으로 해석했습니다. 원본 예약 정보와 대조하세요."

DEFAULT_TIMEZONE = ZoneInfo("Asia/Seoul")

_KIND_NORMALIZATION = {
    "transport": "transport",
    "transportation": "transport",
    "accommodation": "accommodation",
    "hotel": "accommodation",
    "stay": "accommodation",
    "lodging": "accommodation",
}

_TRANSPORT_MODE_NORMALIZATION = {
    "flight": "flight",
    "airplane": "flight",
    "air": "flight",
    "train": "train",
    "rail": "train",
    "railway": "train",
    "intercity_bus": "intercity_bus",
    "bus": "intercity_bus",
    "highway_bus": "intercity_bus",
    "express_bus": "intercity_bus",
}


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

    @field_validator("kind", mode="before")
    @classmethod
    def normalize_kind(cls, value: str) -> str:
        if isinstance(value, str):
            normalized = value.strip().lower()
            return _KIND_NORMALIZATION.get(normalized, normalized)
        return value

    @field_validator("transport_mode", mode="before")
    @classmethod
    def normalize_transport_mode(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            normalized = value.strip().lower()
            if not normalized:
                return None
            return _TRANSPORT_MODE_NORMALIZATION.get(normalized, normalized)
        return value

    @field_validator("booking_url")
    @classmethod
    def validate_booking_url(cls, value: str | None) -> str | None:
        if value is None:
            return None

        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("INVALID_BOOKING_URL")
        return value

    @field_validator("departure_at", "arrival_at", "checkin_at", "checkout_at", mode="before")
    @classmethod
    def validate_and_normalize_datetimes(cls, value: datetime | str | None) -> datetime | None:
        if value is None:
            return None

        dt: datetime
        if isinstance(value, str):
            trimmed = value.strip()
            if not trimmed:
                return None
            try:
                dt = datetime.fromisoformat(trimmed)
            except ValueError as exc:
                raise ValueError("DATETIME_INVALID_ISO") from exc
        elif isinstance(value, datetime):
            dt = value
        else:
            raise ValueError("DATETIME_INVALID_TYPE")

        if dt.tzinfo is None or dt.utcoffset() is None:
            dt = dt.replace(tzinfo=DEFAULT_TIMEZONE)

        return dt

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
