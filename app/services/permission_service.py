from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.trip import Trip, TripMember, TripMemberStatus, TripRole


def get_active_membership(db: Session, trip_id: int, user_id: int) -> TripMember | None:
    stmt = select(TripMember).where(
        TripMember.trip_id == trip_id,
        TripMember.user_id == user_id,
        TripMember.status == TripMemberStatus.ACTIVE.value,
    )
    return db.scalar(stmt)


def require_trip(db: Session, trip_id: int) -> Trip:
    trip = db.get(Trip, trip_id)
    if trip is None:
        raise AppError(404, "TRIP_NOT_FOUND", "여행을 찾을 수 없습니다.")
    return trip


def require_member(db: Session, trip_id: int, user_id: int) -> TripMember:
    """여행 조회 권한: active member만 접근 가능."""
    membership = get_active_membership(db, trip_id, user_id)
    if membership is None:
        raise AppError(403, "FORBIDDEN", "이 여행에 접근할 권한이 없습니다.")
    return membership


def require_owner(db: Session, trip_id: int, user_id: int) -> TripMember:
    membership = require_member(db, trip_id, user_id)
    if membership.role != TripRole.OWNER.value:
        raise AppError(403, "FORBIDDEN", "여행 생성자만 수행할 수 있는 작업입니다.")
    return membership


def require_editor_or_owner(db: Session, trip_id: int, user_id: int) -> TripMember:
    membership = require_member(db, trip_id, user_id)
    if membership.role not in (TripRole.OWNER.value, TripRole.EDITOR.value):
        raise AppError(403, "FORBIDDEN", "일정을 수정할 권한이 없습니다.")
    return membership
