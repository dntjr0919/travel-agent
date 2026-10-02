from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.core.errors import AppError
from app.routers import ai_itinerary, auth, collaborations, itineraries, pages, places, presence, reservation_imports, travel_booking_candidates, trips

app = FastAPI(title="Travel Planner")

app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(auth.router)
app.include_router(trips.router)
app.include_router(itineraries.router)
app.include_router(collaborations.router)
app.include_router(pages.router)
app.include_router(presence.router)
app.include_router(places.router)
app.include_router(reservation_imports.router)
app.include_router(travel_booking_candidates.router)
app.include_router(ai_itinerary.router)

_VALIDATION_CODE_MESSAGES = {
    "INVALID_DATE_RANGE": "시작일은 종료일보다 늦을 수 없습니다.",
    "INVALID_TIME_RANGE": "종료 시각은 시작 시각보다 빠를 수 없습니다.",
}


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail, "code": exc.code})


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Pydantic 검증 오류를 {detail, code} 형태로 통일한다."""
    for error in exc.errors():
        raw_message = str(error.get("msg", ""))
        for code, message in _VALIDATION_CODE_MESSAGES.items():
            if code in raw_message:
                return JSONResponse(status_code=422, content={"detail": message, "code": code})
    return JSONResponse(
        status_code=422,
        content={"detail": "요청 값이 올바르지 않습니다.", "code": "VALIDATION_ERROR"},
    )
