from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.trip import TripCreate, TripOut, TripUpdate
from app.services.trip_service import (
    create_trip,
    delete_trip,
    get_trip_with_role,
    list_trips_for_user,
    update_trip,
)

router = APIRouter(prefix="/api/trips", tags=["trips"])


def _to_out(trip, role: str | None = None) -> TripOut:
    out = TripOut.model_validate(trip)
    out.my_role = role
    return out


@router.get("", response_model=list[TripOut])
def list_trips(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[TripOut]:
    rows = list_trips_for_user(db, current_user.id)
    return [_to_out(trip, role) for trip, role in rows]


@router.post("", response_model=TripOut, status_code=201)
def create(
    data: TripCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> TripOut:
    trip = create_trip(db, current_user, data)
    return _to_out(trip, "owner")


@router.get("/{trip_id}", response_model=TripOut)
def get_trip(
    trip_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> TripOut:
    trip, role = get_trip_with_role(db, trip_id, current_user.id)
    return _to_out(trip, role)


@router.patch("/{trip_id}", response_model=TripOut)
def patch_trip(
    trip_id: int,
    data: TripUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TripOut:
    trip = update_trip(db, trip_id, current_user.id, data)
    return _to_out(trip, "owner")


@router.delete("/{trip_id}", status_code=204, response_model=None)
def remove_trip(
    trip_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> None:
    delete_trip(db, trip_id, current_user.id)
