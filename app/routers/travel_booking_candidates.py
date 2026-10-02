from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.travel_booking_candidate import (
    TravelBookingCandidateCreate,
    TravelBookingCandidateOut,
    TravelBookingCandidateUpdate,
)
from app.services.travel_booking_candidate_service import (
    create_travel_booking_candidate,
    delete_travel_booking_candidate,
    list_travel_booking_candidates,
    update_travel_booking_candidate,
)

router = APIRouter(prefix="/api", tags=["travel booking candidates"])


@router.get("/trips/{trip_id}/booking-candidates", response_model=list[TravelBookingCandidateOut])
def get_travel_booking_candidates(
    trip_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    return list_travel_booking_candidates(db, trip_id, current_user.id)


@router.post(
    "/trips/{trip_id}/booking-candidates",
    response_model=TravelBookingCandidateOut,
    status_code=201,
)
def post_travel_booking_candidate(
    trip_id: int,
    data: TravelBookingCandidateCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    return create_travel_booking_candidate(db, trip_id, current_user, data)


@router.patch("/booking-candidates/{candidate_id}", response_model=TravelBookingCandidateOut)
def patch_travel_booking_candidate(
    candidate_id: int,
    data: TravelBookingCandidateUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    return update_travel_booking_candidate(db, candidate_id, current_user, data)


@router.delete("/booking-candidates/{candidate_id}", status_code=204, response_model=None)
def remove_travel_booking_candidate(
    candidate_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    delete_travel_booking_candidate(db, candidate_id, current_user.id)