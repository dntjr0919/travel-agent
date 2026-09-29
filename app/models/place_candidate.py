from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TZDateTime


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PlaceCandidate(Base):
    """여행별로 보관하는 장소 후보."""

    __tablename__ = "place_candidates"
    __table_args__ = (
        UniqueConstraint(
            "trip_id",
            "provider",
            "external_place_id",
            name="uq_place_candidate_trip_provider_external_id",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    trip_id: Mapped[int] = mapped_column(
        ForeignKey("trips.id"),
        nullable=False,
        index=True,
    )

    provider: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    external_place_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    address: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    latitude: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    longitude: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    category: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    map_url: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )

    source_url: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )

    memo: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_by: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        TZDateTime,
        default=_utcnow,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        TZDateTime,
        default=_utcnow,
        onupdate=_utcnow,
        nullable=False,
    )

    trip = relationship("Trip")
    creator = relationship("User", foreign_keys=[created_by])