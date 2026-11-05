from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.security import hash_token
from app.models.invitation import Invitation
from app.models.trip import TripMember, TripMemberStatus
from app.models.user import User
from app.schemas.invitation import InvitationCreate
from app.services.permission_service import require_owner, require_trip

settings = get_settings()


def create_invitation(db: Session, trip_id: int, inviter: User, data: InvitationCreate) -> tuple[Invitation, str]:
    require_owner(db, trip_id, inviter.id)
    require_trip(db, trip_id)

    raw_token = secrets.token_urlsafe(32)
    invitation = Invitation(
        trip_id=trip_id,
        email=data.email,
        role=data.role,
        token_hash=hash_token(raw_token),
        invited_by=inviter.id,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=settings.invitation_expire_hours),
    )
    db.add(invitation)
    db.commit()
    db.refresh(invitation)

    invite_url = f"{settings.app_base_url}/invitations/{raw_token}"
    return invitation, invite_url


def accept_invitation(db: Session, token: str, user: User) -> Invitation:
    token_hash = hash_token(token)
    invitation = db.scalar(select(Invitation).where(Invitation.token_hash == token_hash))
    if invitation is None:
        raise AppError(404, "INVITATION_NOT_FOUND", "초대장을 찾을 수 없습니다.")

    if invitation.accepted_at is not None:
        raise AppError(410, "INVITATION_EXPIRED", "이미 사용된 초대장입니다.")

    if invitation.expires_at < datetime.now(timezone.utc):
        raise AppError(410, "INVITATION_EXPIRED", "만료된 초대장입니다.")

    if invitation.email.lower() != user.email.lower():
        raise AppError(403, "INVITATION_EMAIL_MISMATCH", "초대받은 이메일과 로그인 계정이 일치하지 않습니다.")

    membership = db.scalar(
        select(TripMember).where(TripMember.trip_id == invitation.trip_id, TripMember.user_id == user.id)
    )
    if membership is None:
        membership = TripMember(
            trip_id=invitation.trip_id,
            user_id=user.id,
            role=invitation.role,
            status=TripMemberStatus.ACTIVE.value,
            invited_by=invitation.invited_by,
        )
        db.add(membership)
    else:
        membership.role = invitation.role
        membership.status = TripMemberStatus.ACTIVE.value

    invitation.accepted_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(invitation)
    return invitation


def list_members(db: Session, trip_id: int) -> list[TripMember]:
    stmt = select(TripMember).where(TripMember.trip_id == trip_id).order_by(TripMember.created_at.asc())
    return list(db.scalars(stmt).all())


def update_member_role(db: Session, trip_id: int, target_user_id: int, owner_id: int, new_role: str) -> TripMember:
    require_owner(db, trip_id, owner_id)
    trip = require_trip(db, trip_id)
    if target_user_id == trip.owner_id:
        raise AppError(403, "FORBIDDEN", "여행 생성자의 권한은 변경할 수 없습니다.")

    membership = db.scalar(
        select(TripMember).where(TripMember.trip_id == trip_id, TripMember.user_id == target_user_id)
    )
    if membership is None:
        raise AppError(404, "TRIP_NOT_FOUND", "구성원을 찾을 수 없습니다.")

    membership.role = new_role
    db.commit()
    db.refresh(membership)
    return membership


def remove_member(db: Session, trip_id: int, target_user_id: int, owner_id: int) -> None:
    require_owner(db, trip_id, owner_id)
    trip = require_trip(db, trip_id)
    if target_user_id == trip.owner_id:
        raise AppError(403, "FORBIDDEN", "여행 생성자는 제거할 수 없습니다.")

    membership = db.scalar(
        select(TripMember).where(TripMember.trip_id == trip_id, TripMember.user_id == target_user_id)
    )
    if membership is None:
        raise AppError(404, "TRIP_NOT_FOUND", "구성원을 찾을 수 없습니다.")

    db.delete(membership)
    db.commit()
