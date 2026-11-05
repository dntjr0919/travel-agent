from __future__ import annotations

import hashlib

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.errors import AppError
from app.core.presence import presence_manager
from app.models.place_candidate import PlaceCandidate
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
from app.services.external_llm_itinerary_service import parse_external_llm_draft
from app.services.itinerary_route_service import calculate_itinerary_routes
from app.services.itinerary_service import (
    create_itineraries,
    create_itinerary,
    delete_itinerary,
    get_itinerary,
    list_itineraries,
    update_itinerary,
)
from app.services.permission_service import require_editor_or_owner, require_trip

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
    background_tasks: BackgroundTasks,
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

    existing_candidates = list(
        db.scalars(select(PlaceCandidate).where(PlaceCandidate.trip_id == trip_id)).all()
    )
    by_ext_id: dict[tuple[str, str], PlaceCandidate] = {
        (c.provider, c.external_place_id): c for c in existing_candidates
    }
    by_name: dict[str, PlaceCandidate] = {
        c.name.strip().lower(): c for c in existing_candidates if c.name and c.name.strip()
    }
    by_map_url: dict[str, PlaceCandidate] = {
        c.map_url.strip(): c for c in existing_candidates if c.map_url and c.map_url.strip()
    }

    candidate_id_by_index: dict[int, int | None] = {}
    newly_created_candidates: list[PlaceCandidate] = []

    for item in selected_items:
        loc_name = (item.location_name or "").strip()[:200]
        if not loc_name:
            candidate_id_by_index[item.index] = None
            continue

        loc_key = loc_name.lower()
        map_url = item.place_url.strip() if item.place_url and item.place_url.strip() else None
        if map_url and len(map_url) <= 255:
            ext_id = map_url
        else:
            raw_ext = f"llm:{loc_key}"
            ext_id = (
                raw_ext
                if len(raw_ext) <= 255
                else f"llm:{hashlib.sha256(loc_key.encode('utf-8')).hexdigest()[:32]}"
            )

        matched = (
            by_ext_id.get(("google", ext_id))
            or by_name.get(loc_key)
            or (by_map_url.get(map_url) if map_url else None)
        )
        if matched is not None:
            if map_url and not matched.map_url:
                matched.map_url = map_url
                by_map_url[map_url] = matched
            candidate_id_by_index[item.index] = matched.id
            continue

        candidate = PlaceCandidate(
            trip_id=trip_id,
            provider="google",
            external_place_id=ext_id,
            name=loc_name,
            map_url=map_url,
            created_by=current_user.id,
        )
        db.add(candidate)
        db.flush()
        by_ext_id[("google", ext_id)] = candidate
        by_name[loc_key] = candidate
        if map_url:
            by_map_url[map_url] = candidate
        candidate_id_by_index[item.index] = candidate.id
        newly_created_candidates.append(candidate)

    create_items = [
        ItineraryCreate(
            title=item.title,
            category="other",
            status="planned",
            start_at=item.start_at,
            end_at=item.end_at,
            location_name=item.location_name,
            memo=item.memo,
            place_candidate_id=candidate_id_by_index.get(item.index),
        )
        for item in selected_items
    ]
    created = create_itineraries(db, trip_id, current_user, create_items)
    for created_candidate in newly_created_candidates:
        background_tasks.add_task(
            presence_manager.broadcast_trip_activity,
            trip_id,
            actor_id=current_user.id,
            actor_name=current_user.display_name,
            entity_type="place_candidate",
            action="created",
            entity_id=created_candidate.id,
            title=created_candidate.name,
        )
    for created_item in created:
        background_tasks.add_task(
            presence_manager.broadcast_trip_activity,
            trip_id,
            actor_id=current_user.id,
            actor_name=current_user.display_name,
            entity_type="itinerary",
            action="created",
            entity_id=created_item["id"],
            title=created_item["title"],
        )
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
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    created = create_itinerary(db, trip_id, current_user, data)
    background_tasks.add_task(
        presence_manager.broadcast_trip_activity,
        trip_id,
        actor_id=current_user.id,
        actor_name=current_user.display_name,
        entity_type="itinerary",
        action="created",
        entity_id=created["id"],
        title=created["title"],
    )
    return created


@router.get("/itineraries/{item_id}", response_model=ItineraryOut)
def get_single_itinerary(
    item_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> dict:
    return get_itinerary(db, item_id, current_user.id)


@router.patch("/itineraries/{item_id}", response_model=ItineraryOut)
def patch_itinerary(
    item_id: int,
    data: ItineraryUpdate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    updated = update_itinerary(db, item_id, current_user, data)
    background_tasks.add_task(
        presence_manager.broadcast_trip_activity,
        updated["trip_id"],
        actor_id=current_user.id,
        actor_name=current_user.display_name,
        entity_type="itinerary",
        action="updated",
        entity_id=updated["id"],
        title=updated["title"],
    )
    return updated


@router.delete("/itineraries/{item_id}", status_code=204, response_model=None)
def remove_itinerary(
    item_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> None:
    delete_itinerary(db, item_id, current_user.id)
