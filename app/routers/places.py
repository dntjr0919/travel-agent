from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.place import (
    PlaceCandidateCreate,
    PlaceCandidateOut,
    PlaceCandidateUpdate,
    PlaceSearchOut,
    PlaceSearchResponse,
)
from app.services.place_candidate_service import (
    create_place_candidate,
    delete_place_candidate,
    list_place_candidates,
    update_place_candidate,
)
from app.services.place_search_service import search_places
from app.services.permission_service import require_member

router = APIRouter(prefix="/api", tags=["places"])

@router.get(
    "/trips/{trip_id}/places/search",
    response_model=PlaceSearchResponse,
)
def search_trip_places(
    trip_id: int,
    scope: str,
    q: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PlaceSearchResponse:
    require_member(db, trip_id, current_user.id)

    provider, results = search_places(scope, q)

    return PlaceSearchResponse(
        provider=provider,
        query=q.strip(),
        results=[
            PlaceSearchOut(
                provider=result.provider,
                external_place_id=result.external_place_id,
                name=result.name,
                address=result.address,
                latitude=result.latitude,
                longitude=result.longitude,
                category=result.category,
                map_url=result.map_url,
                source_url=result.source_url,
            )
            for result in results
        ],
    )

@router.get(
    "/trips/{trip_id}/place-candidates",
    response_model=list[PlaceCandidateOut],
)
def get_place_candidates(
    trip_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    return list_place_candidates(db, trip_id, current_user.id)


@router.post(
    "/trips/{trip_id}/place-candidates",
    response_model=PlaceCandidateOut,
    status_code=201,
)
def create_trip_place_candidate(
    trip_id: int,
    data: PlaceCandidateCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    return create_place_candidate(db, trip_id, current_user, data)


@router.patch(
    "/place-candidates/{candidate_id}",
    response_model=PlaceCandidateOut,
)
def patch_place_candidate(
    candidate_id: int,
    data: PlaceCandidateUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    return update_place_candidate(db, candidate_id, current_user, data)


@router.delete(
    "/place-candidates/{candidate_id}",
    status_code=204,
    response_model=None,
)
def remove_place_candidate(
    candidate_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    delete_place_candidate(db, candidate_id, current_user.id)