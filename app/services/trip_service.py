from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.trip import Trip, TripMember, TripMemberStatus, TripRole
from app.models.user import User
from app.schemas.trip import TripCreate, TripUpdate
from app.services.permission_service import get_active_membership, require_owner, require_trip


def create_trip(db: Session, owner: User, data: TripCreate) -> Trip:
    if data.start_date > data.end_date:
        raise AppError(422, "INVALID_DATE_RANGE", "시작일은 종료일보다 늦을 수 없습니다.")

    trip = Trip(
        title=data.title,
        destination=data.destination,
        start_date=data.start_date,
        end_date=data.end_date,
        timezone=data.timezone,
        owner_id=owner.id,
    )
    db.add(trip)
    db.flush()

    member = TripMember(
        trip_id=trip.id,
        user_id=owner.id,
        role=TripRole.OWNER.value,
        status=TripMemberStatus.ACTIVE.value,
        invited_by=None,
    )
    db.add(member)
    db.commit()
    db.refresh(trip)
    return trip


def list_trips_for_user(db: Session, user_id: int) -> list[tuple[Trip, str]]:
    stmt = (
        select(Trip, TripMember.role)
        .join(TripMember, TripMember.trip_id == Trip.id)
        .where(TripMember.user_id == user_id, TripMember.status == TripMemberStatus.ACTIVE.value)
        .order_by(Trip.start_date.desc())
    )
    return [(trip, role) for trip, role in db.execute(stmt).all()]


def get_trip_with_role(db: Session, trip_id: int, user_id: int) -> tuple[Trip, str]:
    trip = require_trip(db, trip_id)
    membership = get_active_membership(db, trip_id, user_id)
    if membership is None:
        raise AppError(403, "FORBIDDEN", "이 여행에 접근할 권한이 없습니다.")
    return trip, membership.role


def update_trip(db: Session, trip_id: int, user_id: int, data: TripUpdate) -> Trip:
    require_owner(db, trip_id, user_id)
    trip = require_trip(db, trip_id)

    new_start = data.start_date if data.start_date is not None else trip.start_date
    new_end = data.end_date if data.end_date is not None else trip.end_date
    if new_start > new_end:
        raise AppError(422, "INVALID_DATE_RANGE", "시작일은 종료일보다 늦을 수 없습니다.")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(trip, field, value)

    db.commit()
    db.refresh(trip)
    return trip


def delete_trip(db: Session, trip_id: int, user_id: int) -> None:
    require_owner(db, trip_id, user_id)
    trip = require_trip(db, trip_id)
    db.delete(trip)
    db.commit()
