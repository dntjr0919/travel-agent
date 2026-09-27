from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TZDateTime


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, default=_utcnow, onupdate=_utcnow, nullable=False)

    owned_trips = relationship("Trip", back_populates="owner", foreign_keys="Trip.owner_id")
