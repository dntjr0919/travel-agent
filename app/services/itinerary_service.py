from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.errors import AppError
from app.models.itinerary import ItineraryItem, ItineraryStatus
from app.models.trip import Trip
from app.models.user import User
from app.schemas.itinerary import ItineraryCreate, ItineraryUpdate
from app.services.permission_service import require_editor_or_owner, require_member, require_trip


def _check_within_trip_range(trip: Trip, moment: datetime) -> None:
    try:
        tz = ZoneInfo(trip.timezone)
    except Exception:
        tz = ZoneInfo("UTC")
    local_date = moment.astimezone(tz).date()
    if local_date < trip.start_date or local_date > trip.end_date:
        raise AppError(422, "INVALID_DATE_RANGE", "일정 날짜가 여행 기간을 벗어났습니다.")


def _serialize(db: Session, item: ItineraryItem) -> dict:
    creator = item.creator if "creator" in item.__dict__ else db.get(User, item.created_by)
    updater = item.updater if "updater" in item.__dict__ else db.get(User, item.updated_by)
    return {
        "id": item.id,
        "trip_id": item.trip_id,
        "title": item.title,
        "category": item.category,
        "status": item.status,
        "start_at": item.start_at,
        "end_at": item.end_at,
        "location_name": item.location_name,
        "memo": item.memo,
        "place_candidate_id": item.place_candidate_id,
        "place_provider": item.place_provider,
        "external_place_id": item.external_place_id,
        "latitude": item.latitude,
        "longitude": item.longitude,
        "created_by": item.created_by,
        "updated_by": item.updated_by,
        "created_by_name": creator.display_name if creator else "알 수 없음",
        "updated_by_name": updater.display_name if updater else "알 수 없음",
        "version": item.version,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


def list_itineraries(db: Session, trip_id: int, user_id: int) -> list[dict]:
    require_member(db, trip_id, user_id)
    stmt = (
        select(ItineraryItem)
        .options(
            joinedload(ItineraryItem.creator),
            joinedload(ItineraryItem.updater),
        )
        .where(ItineraryItem.trip_id == trip_id)
        .order_by(ItineraryItem.start_at.asc().nulls_last(), ItineraryItem.id.asc())
    )
    items = db.scalars(stmt).all()
    return [_serialize(db, item) for item in items]


def create_itinerary(db: Session, trip_id: int, user: User, data: ItineraryCreate) -> dict:
    require_editor_or_owner(db, trip_id, user.id)
    trip = require_trip(db, trip_id)

    if data.start_at:
        _check_within_trip_range(trip, data.start_at)
    if data.end_at:
        _check_within_trip_range(trip, data.end_at)

    item = ItineraryItem(
        trip_id=trip_id,
        title=data.title,
        category=data.category,
        status=data.status.value,
        start_at=data.start_at,
        end_at=data.end_at,
        location_name=data.location_name,
        memo=data.memo,
        place_candidate_id=data.place_candidate_id,
        place_provider=data.place_provider,
        external_place_id=data.external_place_id,
        latitude=data.latitude,
        longitude=data.longitude,
        created_by=user.id,
        updated_by=user.id,
        version=1,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return _serialize(db, item)


def create_itineraries(db: Session, trip_id: int, user: User, items: list[ItineraryCreate]) -> list[dict]:
    try:
        require_editor_or_owner(db, trip_id, user.id)
        trip = require_trip(db, trip_id)

        itinerary_items = []
        for data in items:
            if data.start_at:
                _check_within_trip_range(trip, data.start_at)
            if data.end_at:
                _check_within_trip_range(trip, data.end_at)
            itinerary_items.append(
                ItineraryItem(
                    trip_id=trip_id,
                    title=data.title,
                    category=data.category,
                    status=data.status.value,
                    start_at=data.start_at,
                    end_at=data.end_at,
                    location_name=data.location_name,
                    memo=data.memo,
                    place_candidate_id=data.place_candidate_id,
                    place_provider=data.place_provider,
                    external_place_id=data.external_place_id,
                    latitude=data.latitude,
                    longitude=data.longitude,
                    created_by=user.id,
                    updated_by=user.id,
                    version=1,
                )
            )

        db.add_all(itinerary_items)
        db.flush()
        serialized = [_serialize(db, item) for item in itinerary_items]
        db.commit()
        return serialized
    except Exception:
        db.rollback()
        raise


def get_itinerary(db: Session, item_id: int, user_id: int) -> dict:
    item = db.get(ItineraryItem, item_id)
    if item is None:
        raise AppError(404, "ITINERARY_NOT_FOUND", "일정을 찾을 수 없습니다.")
    require_member(db, item.trip_id, user_id)
    return _serialize(db, item)


def update_itinerary(db: Session, item_id: int, user: User, data: ItineraryUpdate) -> dict:
    item = db.get(ItineraryItem, item_id)
    if item is None:
        raise AppError(404, "ITINERARY_NOT_FOUND", "일정을 찾을 수 없습니다.")

    require_editor_or_owner(db, item.trip_id, user.id)
    trip = require_trip(db, item.trip_id)

    if item.version != data.version:
        raise AppError(
            409,
            "ITINERARY_VERSION_CONFLICT",
            "다른 사용자가 이미 수정했습니다. 최신 내용을 불러온 뒤 다시 수정하세요.",
        )

    new_start = data.start_at if data.start_at is not None else item.start_at
    new_end = data.end_at if data.end_at is not None else item.end_at
    if new_start and new_end and new_start > new_end:
        raise AppError(422, "INVALID_TIME_RANGE", "종료 시각은 시작 시각보다 빠를 수 없습니다.")
    if new_start:
        _check_within_trip_range(trip, new_start)
    if new_end:
        _check_within_trip_range(trip, new_end)

    update_fields = data.model_dump(exclude_unset=True, exclude={"version"})

    if "status" in update_fields:
        update_fields["status"] = data.status.value if data.status is not None else None

    for field, value in update_fields.items():
        setattr(item, field, value)

    item.updated_by = user.id
    item.version += 1

    db.commit()
    db.refresh(item)
    return _serialize(db, item)


def delete_itinerary(db: Session, item_id: int, user_id: int) -> None:
    item = db.get(ItineraryItem, item_id)
    if item is None:
        raise AppError(404, "ITINERARY_NOT_FOUND", "일정을 찾을 수 없습니다.")
    require_editor_or_owner(db, item.trip_id, user_id)
    db.delete(item)
    db.commit()
