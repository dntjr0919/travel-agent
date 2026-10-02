from __future__ import annotations

from sqlalchemy import case, select
from sqlalchemy.orm import Session
from pydantic import ValidationError

from app.core.errors import AppError
from app.models.travel_booking_candidate import TravelBookingCandidate
from app.models.trip import Trip
from app.models.user import User
from app.schemas.travel_booking_candidate import (
    TravelBookingCandidateCreate,
    TravelBookingCandidateUpdate,
)
from app.services.permission_service import require_editor_or_owner, require_member, require_trip


def _validate_candidate_fields(values: dict) -> TravelBookingCandidateCreate:
    try:
        return TravelBookingCandidateCreate.model_validate(values)
    except ValidationError as exc:
        raise AppError(422, "VALIDATION_ERROR", "교통·숙박 후보 정보가 올바르지 않습니다.") from exc


def _serialize(db: Session, candidate: TravelBookingCandidate) -> dict:
    creator = db.get(User, candidate.created_by)
    return {
        "id": candidate.id,
        "trip_id": candidate.trip_id,
        "kind": candidate.kind,
        "title": candidate.title,
        "provider_name": candidate.provider_name,
        "booking_url": candidate.booking_url,
        "price_amount": candidate.price_amount,
        "currency": candidate.currency,
        "memo": candidate.memo,
        "transport_mode": candidate.transport_mode,
        "service_number": candidate.service_number,
        "departure_name": candidate.departure_name,
        "arrival_name": candidate.arrival_name,
        "departure_at": candidate.departure_at,
        "arrival_at": candidate.arrival_at,
        "accommodation_name": candidate.accommodation_name,
        "check_in_at": candidate.check_in_at,
        "check_out_at": candidate.check_out_at,
        "created_by": candidate.created_by,
        "created_by_name": creator.display_name if creator else "알 수 없음",
        "created_at": candidate.created_at,
        "updated_at": candidate.updated_at,
    }


def _candidate_or_404(db: Session, candidate_id: int) -> TravelBookingCandidate:
    candidate = db.get(TravelBookingCandidate, candidate_id)
    if candidate is None:
        raise AppError(404, "TRAVEL_BOOKING_CANDIDATE_NOT_FOUND", "교통·숙박 후보를 찾을 수 없습니다.")
    return candidate


def list_travel_booking_candidates(db: Session, trip_id: int, user_id: int) -> list[dict]:
    require_trip(db, trip_id)
    require_member(db, trip_id, user_id)
    sort_datetime = case(
        (TravelBookingCandidate.kind == "transport", TravelBookingCandidate.departure_at),
        (TravelBookingCandidate.kind == "accommodation", TravelBookingCandidate.check_in_at),
    )
    stmt = (
        select(TravelBookingCandidate)
        .where(TravelBookingCandidate.trip_id == trip_id)
        .order_by(
            TravelBookingCandidate.kind.asc(),
            sort_datetime.asc().nulls_last(),
            TravelBookingCandidate.created_at.desc(),
            TravelBookingCandidate.id.asc(),
        )
    )
    return [_serialize(db, item) for item in db.scalars(stmt).all()]


def create_travel_booking_candidate(
    db: Session,
    trip_id: int,
    user: User,
    data: TravelBookingCandidateCreate,
) -> dict:
    require_trip(db, trip_id)
    require_editor_or_owner(db, trip_id, user.id)
    values = _validate_candidate_fields(data.model_dump()).model_dump()
    if values["booking_url"] is not None:
        values["booking_url"] = str(values["booking_url"])
    candidate = TravelBookingCandidate(trip_id=trip_id, created_by=user.id, **values)
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    return _serialize(db, candidate)


def update_travel_booking_candidate(
    db: Session,
    candidate_id: int,
    user: User,
    data: TravelBookingCandidateUpdate,
) -> dict:
    candidate = _candidate_or_404(db, candidate_id)
    require_editor_or_owner(db, candidate.trip_id, user.id)
    values = {**{field: getattr(candidate, field) for field in TravelBookingCandidateCreate.model_fields}, **data.model_dump(exclude_unset=True)}
    if values["booking_url"] is not None:
        values["booking_url"] = str(values["booking_url"])
    validated = _validate_candidate_fields(values)
    for field, value in validated.model_dump().items():
        setattr(candidate, field, str(value) if field == "booking_url" and value is not None else value)
    db.commit()
    db.refresh(candidate)
    return _serialize(db, candidate)


def delete_travel_booking_candidate(db: Session, candidate_id: int, user_id: int) -> None:
    candidate = _candidate_or_404(db, candidate_id)
    require_editor_or_owner(db, candidate.trip_id, user_id)
    db.delete(candidate)
    db.commit()