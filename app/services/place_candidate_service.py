from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.core.errors import AppError
from app.models.place_candidate import PlaceCandidate
from app.models.user import User
from app.schemas.place import PlaceCandidateCreate, PlaceCandidateUpdate
from app.services.permission_service import (
    require_editor_or_owner,
    require_member,
    require_trip,
)


def _serialize(db: Session, candidate: PlaceCandidate) -> dict:
    creator = candidate.creator if "creator" in candidate.__dict__ else db.get(User, candidate.created_by)

    return {
        "id": candidate.id,
        "trip_id": candidate.trip_id,
        "provider": candidate.provider,
        "external_place_id": candidate.external_place_id,
        "name": candidate.name,
        "address": candidate.address,
        "latitude": candidate.latitude,
        "longitude": candidate.longitude,
        "category": candidate.category,
        "map_url": candidate.map_url,
        "source_url": candidate.source_url,
        "memo": candidate.memo,
        "created_by": candidate.created_by,
        "created_by_name": creator.display_name if creator else "알 수 없음",
        "created_at": candidate.created_at,
        "updated_at": candidate.updated_at,
    }


def list_place_candidates(
    db: Session,
    trip_id: int,
    user_id: int,
) -> list[dict]:
    require_member(db, trip_id, user_id)

    stmt = (
        select(PlaceCandidate)
        .options(joinedload(PlaceCandidate.creator))
        .where(PlaceCandidate.trip_id == trip_id)
        .order_by(PlaceCandidate.created_at.desc())
    )
    candidates = db.scalars(stmt).all()

    return [_serialize(db, candidate) for candidate in candidates]


def create_place_candidate(
    db: Session,
    trip_id: int,
    user: User,
    data: PlaceCandidateCreate,
) -> dict:
    require_editor_or_owner(db, trip_id, user.id)
    require_trip(db, trip_id)

    candidate = PlaceCandidate(
        trip_id=trip_id,
        provider=data.provider,
        external_place_id=data.external_place_id,
        name=data.name,
        address=data.address,
        latitude=data.latitude,
        longitude=data.longitude,
        category=data.category,
        map_url=str(data.map_url) if data.map_url else None,
        source_url=str(data.source_url) if data.source_url else None,
        memo=data.memo,
        created_by=user.id,
    )

    db.add(candidate)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise AppError(
            409,
            "PLACE_CANDIDATE_ALREADY_EXISTS",
            "이미 이 여행의 장소 후보에 저장되어 있습니다.",
        )

    db.refresh(candidate)
    return _serialize(db, candidate)


def update_place_candidate(
    db: Session,
    candidate_id: int,
    user: User,
    data: PlaceCandidateUpdate,
) -> dict:
    candidate = db.get(PlaceCandidate, candidate_id)

    if candidate is None:
        raise AppError(
            404,
            "PLACE_CANDIDATE_NOT_FOUND",
            "장소 후보를 찾을 수 없습니다.",
        )

    require_editor_or_owner(db, candidate.trip_id, user.id)

    candidate.memo = data.memo
    db.commit()
    db.refresh(candidate)

    return _serialize(db, candidate)


def delete_place_candidate(
    db: Session,
    candidate_id: int,
    user_id: int,
) -> None:
    candidate = db.get(PlaceCandidate, candidate_id)

    if candidate is None:
        raise AppError(
            404,
            "PLACE_CANDIDATE_NOT_FOUND",
            "장소 후보를 찾을 수 없습니다.",
        )

    require_editor_or_owner(db, candidate.trip_id, user_id)

    db.delete(candidate)
    db.commit()