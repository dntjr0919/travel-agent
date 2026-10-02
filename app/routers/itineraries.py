from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.external_llm_itinerary import (
    ExternalLlmItineraryAnalyzeRequest,
    ExternalLlmItineraryAnalyzeResponse,
    ExternalLlmItineraryImportRequest,
    ExternalLlmItineraryImportResponse,
)
from app.schemas.itinerary import (
    ItineraryCreate,
    ItineraryOut,
    ItineraryRouteRequest,
    ItineraryRouteResponse,
    ItineraryUpdate,
)
from app.services.itinerary_service import (
    create_itinerary,
    create_itineraries,
    delete_itinerary,
    get_itinerary,
    list_itineraries,
    update_itinerary,
)
from app.services.itinerary_route_service import calculate_itinerary_routes
from app.services.external_llm_itinerary_service import parse_external_llm_draft
from app.services.permission_service import require_editor_or_owner, require_trip
from app.core.errors import AppError

router = APIRouter(prefix="/api", tags=["itineraries"])


@router.post(
    "/trips/{trip_id}/external-llm-itinerary/analyze",
    response_model=ExternalLlmItineraryAnalyzeResponse,
)
def analyze_external_llm_itinerary(
    trip_id: int,
    data: ExternalLlmItineraryAnalyzeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    trip = require_trip(db, trip_id)
    require_editor_or_owner(db, trip_id, current_user.id)
    items = parse_external_llm_draft(data.raw_json, trip)
    return {
        "items": [
            {
                "index": item.index,
                "date": item.date.isoformat() if item.date else None,
                "title": item.title,
                "valid": item.valid,
                "error": item.error,
                "warning": None,
            }
            for item in items
        ]
    }


@router.post(
    "/trips/{trip_id}/external-llm-itinerary/import",
    response_model=ExternalLlmItineraryImportResponse,
)
def import_external_llm_itinerary(
    trip_id: int,
    data: ExternalLlmItineraryImportRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    require_editor_or_owner(db, trip_id, current_user.id)
    trip = require_trip(db, trip_id)
    if len(set(data.selected_indices)) != len(data.selected_indices):
        raise AppError(422, "EXTERNAL_LLM_INVALID_SELECTION", "같은 일정을 중복 선택할 수 없습니다.")

    parsed_items = parse_external_llm_draft(data.raw_json, trip)
    by_index = {item.index: item for item in parsed_items}
    selected_items = []
    for index in data.selected_indices:
        item = by_index.get(index)
        if item is None:
            raise AppError(422, "EXTERNAL_LLM_INVALID_SELECTION", "선택한 일정 번호가 올바르지 않습니다.")
        if not item.valid:
            raise AppError(422, "EXTERNAL_LLM_INVALID_SELECTION", item.error or "선택한 일정이 올바르지 않습니다.")
        selected_items.append(item)

    create_items = [
        ItineraryCreate(
            title=item.title,
            category="other",
            status="planned",
            start_at=item.start_at,
            end_at=item.end_at,
            location_name=item.location_name,
            memo=item.memo,
        )
        for item in selected_items
    ]
    created = create_itineraries(db, trip_id, current_user, create_items)
    return {"created_count": len(created), "items": created}


@router.post(
    "/trips/{trip_id}/itinerary-routes",
    response_model=ItineraryRouteResponse,
)
def post_trip_itinerary_routes(
    trip_id: int,
    data: ItineraryRouteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ItineraryRouteResponse:
    return calculate_itinerary_routes(db, trip_id, current_user.id, data)


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
