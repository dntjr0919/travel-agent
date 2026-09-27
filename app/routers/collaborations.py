from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.invitation import InvitationAcceptResult, InvitationCreate, InvitationOut
from app.schemas.trip import MemberRoleUpdate, TripMemberOut
from app.services.invitation_service import (
    accept_invitation,
    create_invitation,
    list_members,
    remove_member,
    update_member_role,
)
from app.services.permission_service import require_member

router = APIRouter(prefix="/api", tags=["collaboration"])


@router.get("/trips/{trip_id}/members", response_model=list[TripMemberOut])
def get_members(
    trip_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[TripMemberOut]:
    require_member(db, trip_id, current_user.id)
    members = list_members(db, trip_id)
    return [
        TripMemberOut(
            id=m.id,
            trip_id=m.trip_id,
            user_id=m.user_id,
            role=m.role,
            status=m.status,
            joined_at=m.joined_at,
            email=m.user.email,
            display_name=m.user.display_name,
        )
        for m in members
    ]


@router.post("/trips/{trip_id}/invitations", response_model=InvitationOut, status_code=201)
def create_trip_invitation(
    trip_id: int,
    data: InvitationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InvitationOut:
    invitation, invite_url = create_invitation(db, trip_id, current_user, data)
    return InvitationOut(
        id=invitation.id,
        trip_id=invitation.trip_id,
        email=invitation.email,
        role=invitation.role,
        expires_at=invitation.expires_at,
        accepted_at=invitation.accepted_at,
        created_at=invitation.created_at,
        invite_url=invite_url,
    )


@router.post("/invitations/{token}/accept", response_model=InvitationAcceptResult)
def accept_trip_invitation(
    token: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> InvitationAcceptResult:
    invitation = accept_invitation(db, token, current_user)
    return InvitationAcceptResult(trip_id=invitation.trip_id, role=invitation.role)


@router.patch("/trips/{trip_id}/members/{user_id}", response_model=TripMemberOut)
def patch_member_role(
    trip_id: int,
    user_id: int,
    data: MemberRoleUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TripMemberOut:
    member = update_member_role(db, trip_id, user_id, current_user.id, data.role)
    return TripMemberOut(
        id=member.id,
        trip_id=member.trip_id,
        user_id=member.user_id,
        role=member.role,
        status=member.status,
        joined_at=member.joined_at,
        email=member.user.email,
        display_name=member.user.display_name,
    )


@router.delete("/trips/{trip_id}/members/{user_id}", status_code=204, response_model=None)
def delete_member(
    trip_id: int,
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    remove_member(db, trip_id, user_id, current_user.id)
