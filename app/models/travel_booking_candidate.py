from __future__ import annotations

from datetime import datetime

from sqlalchemy import Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TZDateTime, utcnow


class TravelBookingCandidate(Base):
    __tablename__ = "travel_booking_candidates"

    id: Mapped[int] = mapped_column(primary_key=True)
    trip_id: Mapped[int] = mapped_column(ForeignKey("trips.id"), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    provider_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    booking_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    price_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str | None] = mapped_column(String(12), nullable=True)
    memo: Mapped[str | None] = mapped_column(Text, nullable=True)
    transport_mode: Mapped[str | None] = mapped_column(String(30), nullable=True)
    service_number: Mapped[str | None] = mapped_column(String(80), nullable=True)
    departure_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    arrival_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    departure_at: Mapped[datetime | None] = mapped_column(TZDateTime, nullable=True)
    arrival_at: Mapped[datetime | None] = mapped_column(TZDateTime, nullable=True)
    accommodation_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    check_in_at: Mapped[datetime | None] = mapped_column(TZDateTime, nullable=True)
    check_out_at: Mapped[datetime | None] = mapped_column(TZDateTime, nullable=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow, onupdate=utcnow, nullable=False)

    trip = relationship("Trip", back_populates="booking_candidates")
    creator = relationship("User", foreign_keys=[created_by])