from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class InvitationCreate(BaseModel):
    email: EmailStr
    role: str = Field(pattern="^(editor|viewer)$")


class InvitationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    trip_id: int
    email: str
    role: str
    expires_at: datetime
    accepted_at: datetime | None
    created_at: datetime
    invite_url: str


class InvitationAcceptResult(BaseModel):
    trip_id: int
    role: str
