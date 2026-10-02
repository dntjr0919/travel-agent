from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TZDateTime


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ItineraryCategory(str, enum.Enum):
    TRANSPORTATION = "transportation"
    ACCOMMODATION = "accommodation"
    SIGHTSEEING = "sightseeing"
    FOOD = "food"
    SHOPPING = "shopping"
    OTHER = "other"

class ItineraryStatus(str, enum.Enum):
    PLANNED = "planned"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class ItineraryItem(Base):
    __tablename__ = "itinerary_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    trip_id: Mapped[int] = mapped_column(ForeignKey("trips.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default=ItineraryStatus.PLANNED.value)  
    category: Mapped[str] = mapped_column(String(30), nullable=False, default=ItineraryCategory.OTHER.value)
    start_at: Mapped[datetime | None] = mapped_column(TZDateTime, nullable=True)
    end_at: Mapped[datetime | None] = mapped_column(TZDateTime, nullable=True)
    location_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    memo: Mapped[str | None] = mapped_column(Text, nullable=True)
    place_candidate_id: Mapped[int | None] = mapped_column(nullable=True)
    place_provider: Mapped[str | None] = mapped_column(String(30), nullable=True)
    external_place_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    updated_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, default=_utcnow, onupdate=_utcnow, nullable=False)

    trip = relationship("Trip", back_populates="itinerary_items")
    creator = relationship("User", foreign_keys=[created_by])
    updater = relationship("User", foreign_keys=[updated_by])
