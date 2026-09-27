from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.itinerary import ItineraryCreate, ItineraryOut, ItineraryUpdate
from app.services.itinerary_service import (
    create_itinerary,
    delete_itinerary,
    get_itinerary,
    list_itineraries,
    update_itinerary,
)

router = APIRouter(prefix="/api", tags=["itineraries"])


@router.get("/trips/{trip_id}/itineraries", response_model=list[ItineraryOut])
def list_trip_itineraries(
    trip_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[dict]:
    return list_itineraries(db, trip_id, current_user.id)


@router.post("/trips/{trip_id}/itineraries", response_model=ItineraryOut, status_code=201)
def create_trip_itinerary(
    trip_id: int,
    data: ItineraryCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    return create_itinerary(db, trip_id, current_user, data)


@router.get("/itineraries/{item_id}", response_model=ItineraryOut)
def get_single_itinerary(
    item_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> dict:
    return get_itinerary(db, item_id, current_user.id)


@router.patch("/itineraries/{item_id}", response_model=ItineraryOut)
def patch_itinerary(
    item_id: int,
    data: ItineraryUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    return update_itinerary(db, item_id, current_user, data)


@router.delete("/itineraries/{item_id}", status_code=204, response_model=None)
def remove_itinerary(
    item_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> None:
    delete_itinerary(db, item_id, current_user.id)
