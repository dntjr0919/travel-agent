from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, TypeAdapter, field_validator, model_validator

_HTTP_URL_ADAPTER = TypeAdapter(AnyHttpUrl)


def _validate_booking_url(value: str | None) -> str | None:
    if value is None:
        return None
    return str(_HTTP_URL_ADAPTER.validate_python(value))


def _comparable_datetime(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


class TravelBookingCandidateFields(BaseModel):
    kind: Literal["transport", "accommodation"]
    title: str = Field(min_length=1, max_length=200)
    provider_name: str | None = Field(default=None, max_length=120)
    booking_url: str | None = Field(default=None, max_length=1000)
    price_amount: float | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, max_length=12)
    memo: str | None = None
    transport_mode: Literal["flight", "train", "intercity_bus", "local_transit", "other"] | None = None
    service_number: str | None = Field(default=None, max_length=80)
    departure_name: str | None = Field(default=None, max_length=200)
    arrival_name: str | None = Field(default=None, max_length=200)
    departure_at: datetime | None = None
    arrival_at: datetime | None = None
    accommodation_name: str | None = Field(default=None, max_length=200)
    check_in_at: datetime | None = None
    check_out_at: datetime | None = None

    @field_validator("title", "provider_name", "service_number", "departure_name", "arrival_name", "accommodation_name")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip()

    @field_validator("title")
    @classmethod
    def title_is_not_blank(cls, value: str) -> str:
        if not value:
            raise ValueError("title is required")
        return value

    @field_validator("booking_url")
    @classmethod
    def validate_booking_url(cls, value: str | None) -> str | None:
        return _validate_booking_url(value)

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: Any) -> Any:
        if value is None:
            return None
        if not isinstance(value, str):
            return value
        normalized = value.strip()
        if len(normalized) > 12:
            raise ValueError("currency must be at most 12 characters")
        return normalized or None

    @model_validator(mode="after")
    def validate_kind_fields(self) -> "TravelBookingCandidateFields":
        if self.kind == "transport":
            if not self.transport_mode:
                raise ValueError("transport_mode is required for transport candidates")
            if self.departure_at and self.arrival_at and _comparable_datetime(self.arrival_at) <= _comparable_datetime(self.departure_at):
                raise ValueError("arrival_at must be after departure_at")
            if any((self.accommodation_name, self.check_in_at, self.check_out_at)):
                raise ValueError("accommodation fields are not allowed for transport candidates")
        else:
            if not self.accommodation_name:
                raise ValueError("accommodation_name is required for accommodation candidates")
            if self.check_in_at and self.check_out_at and _comparable_datetime(self.check_out_at) <= _comparable_datetime(self.check_in_at):
                raise ValueError("check_out_at must be after check_in_at")
            if any((self.transport_mode, self.service_number, self.departure_name, self.arrival_name, self.departure_at, self.arrival_at)):
                raise ValueError("transport fields are not allowed for accommodation candidates")
        return self


class TravelBookingCandidateCreate(TravelBookingCandidateFields):
    pass


class TravelBookingCandidateUpdate(BaseModel):
    kind: Literal["transport", "accommodation"] | None = None
    title: str | None = Field(default=None, min_length=1, max_length=200)
    provider_name: str | None = Field(default=None, max_length=120)
    booking_url: str | None = Field(default=None, max_length=1000)
    price_amount: float | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, max_length=12)
    memo: str | None = None
    transport_mode: Literal["flight", "train", "intercity_bus", "local_transit", "other"] | None = None
    service_number: str | None = Field(default=None, max_length=80)
    departure_name: str | None = Field(default=None, max_length=200)
    arrival_name: str | None = Field(default=None, max_length=200)
    departure_at: datetime | None = None
    arrival_at: datetime | None = None
    accommodation_name: str | None = Field(default=None, max_length=200)
    check_in_at: datetime | None = None
    check_out_at: datetime | None = None

    @field_validator("title", "provider_name", "service_number", "departure_name", "arrival_name", "accommodation_name")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip()

    @field_validator("title")
    @classmethod
    def title_is_not_blank(cls, value: str | None) -> str | None:
        if value is not None and not value:
            raise ValueError("title cannot be blank")
        return value

    @field_validator("booking_url")
    @classmethod
    def validate_booking_url(cls, value: str | None) -> str | None:
        return _validate_booking_url(value)

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: Any) -> Any:
        if value is None:
            return None
        if not isinstance(value, str):
            return value
        normalized = value.strip()
        if len(normalized) > 12:
            raise ValueError("currency must be at most 12 characters")
        return normalized or None


class TravelBookingCandidateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    trip_id: int
    kind: str
    title: str
    provider_name: str | None
    booking_url: str | None
    price_amount: float | None
    currency: str | None
    memo: str | None
    transport_mode: str | None
    service_number: str | None
    departure_name: str | None
    arrival_name: str | None
    departure_at: datetime | None
    arrival_at: datetime | None
    accommodation_name: str | None
    check_in_at: datetime | None
    check_out_at: datetime | None
    created_by: int
    created_by_name: str
    created_at: datetime
    updated_at: datetime