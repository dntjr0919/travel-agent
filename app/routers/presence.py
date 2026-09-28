from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.presence import presence_manager
from app.core.security import SESSION_COOKIE_NAME, read_session_token
from app.models.user import User
from app.services.permission_service import require_member

router = APIRouter(tags=["presence"])


@router.websocket("/ws/trips/{trip_id}/presence")
async def trip_presence(websocket: WebSocket, trip_id: int) -> None:
    """여행 상세 페이지의 현재 접속자 목록을 실시간으로 전달한다."""
    token = websocket.cookies.get(SESSION_COOKIE_NAME)
    user_id = read_session_token(token) if token else None

    if user_id is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    db: Session = SessionLocal()

    try:
        user = db.get(User, user_id)

        if user is None:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        require_member(db, trip_id, user.id)

        await presence_manager.connect(
            trip_id=trip_id,
            user_id=user.id,
            display_name=user.display_name,
            websocket=websocket,
        )

        while True:
            await websocket.receive_text()

    except WebSocketDisconnect:
        await presence_manager.disconnect(
            trip_id=trip_id,
            user_id=user_id,
            websocket=websocket,
        )
    finally:
        db.close()