from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.errors import AppError
from app.models.user import User
from app.schemas.reservation_import import ReservationImportAnalyzeOut
from app.services.permission_service import require_editor_or_owner, require_trip
from app.services.reservation_import_service import MAX_IMAGE_BYTES, analyze_reservation_image_draft

router = APIRouter(prefix="/api", tags=["reservation-imports"])


@router.post(
    "/trips/{trip_id}/reservation-imports/analyze-image",
    response_model=ReservationImportAnalyzeOut,
)
async def analyze_reservation_image(
    trip_id: int,
    file: UploadFile = File(...),
    booking_url: str | None = Form(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReservationImportAnalyzeOut:
    require_trip(db, trip_id)
    require_editor_or_owner(db, trip_id, current_user.id)

    image_bytes = b""

    try:
        image_bytes = await file.read(MAX_IMAGE_BYTES + 1)

        if not image_bytes:
            raise AppError(
                422,
                "RESERVATION_IMPORT_EMPTY_FILE",
                "이미지 파일을 업로드하세요.",
            )

        return analyze_reservation_image_draft(
            image_bytes=image_bytes,
            content_type=file.content_type,
            booking_url=booking_url,
        )
    finally:
        await file.close()
        image_bytes = b""
