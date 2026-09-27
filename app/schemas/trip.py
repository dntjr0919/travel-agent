from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TripCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    destination: str | None = Field(default=None, max_length=200)
    start_date: date
    end_date: date
    timezone: str = Field(default="Asia/Seoul", max_length=64)

    @model_validator(mode="after")
    def check_date_range(self) -> "TripCreate":
        if self.start_date > self.end_date:
            raise ValueError("INVALID_DATE_RANGE")
        return self


class TripUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    destination: str | None = Field(default=None, max_length=200)
    start_date: date | None = None
    end_date: date | None = None
    timezone: str | None = Field(default=None, max_length=64)


class TripOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    destination: str | None
    start_date: date
    end_date: date
    timezone: str
    owner_id: int
    created_at: datetime
    updated_at: datetime
    my_role: str | None = None


class TripMemberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    trip_id: int
    user_id: int
    role: str
    status: str
    joined_at: datetime
    email: str
    display_name: str


class MemberRoleUpdate(BaseModel):
    role: str = Field(pattern="^(editor|viewer)$")
