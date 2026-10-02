from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.errors import AppError
from app.models.user import User
from app.schemas.ai_itinerary import AiItineraryDraftCreate, AiItineraryDraftOut
from app.services.ai_itinerary_service import create_ai_itinerary_draft
from app.services.permission_service import require_editor_or_owner, require_trip

router = APIRouter(prefix="/api", tags=["ai-itinerary"])


@router.post(
    "/trips/{trip_id}/ai-itinerary-drafts",
    response_model=AiItineraryDraftOut,
)
def create_ai_itinerary_draft_endpoint(
    trip_id: int,
    data: AiItineraryDraftCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AiItineraryDraftOut:
    trip = require_trip(db, trip_id)
    require_editor_or_owner(db, trip_id, current_user.id)

    destination = (trip.destination or "").strip()
    if not destination:
        raise AppError(422, "AI_ITINERARY_DESTINATION_REQUIRED", "여행지(destination)를 먼저 입력하세요.")

    return create_ai_itinerary_draft(
        destination=destination,
        start_date=trip.start_date,
        end_date=trip.end_date,
        timezone=trip.timezone,
        style=data.style,
        interests=data.interests,
        pace=data.pace,
        model=data.model,
    )
