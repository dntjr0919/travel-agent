from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.core.config import get_settings
from app.core.dependencies import get_current_user_optional
from app.models.user import User

router = APIRouter(tags=["pages"])
templates = Jinja2Templates(directory="app/templates")

_STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

def get_static_version(path: str) -> str:
    """정적 파일의 실제 파일 수정 시간(mtime)을 버전 문자열로 반환한다."""
    normalized = path.lstrip("/")
    if normalized.startswith("app/static/"):
        rel_path = normalized[len("app/static/"):]
    elif normalized.startswith("static/"):
        rel_path = normalized[len("static/"):]
    else:
        rel_path = normalized

    file_path = _STATIC_DIR / rel_path
    try:
        if file_path.is_file():
            return str(int(file_path.stat().st_mtime))
    except (OSError, ValueError):
        pass
    return "1"


templates.env.globals["static_v"] = get_static_version
templates.env.globals["get_static_version"] = get_static_version


@router.get("/")
def index(request: Request, user: User | None = Depends(get_current_user_optional)):
    return RedirectResponse(url="/trips" if user else "/login")


@router.get("/register")
def register_page(request: Request):
    return templates.TemplateResponse(request, "register.html", {})


@router.get("/login")
def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html", {})


@router.get("/forgot-password")
def forgot_password_page(request: Request):
    return templates.TemplateResponse(request, "forgot_password.html", {})


@router.get("/reset-password/{token}")
def reset_password_page(request: Request, token: str):
    return templates.TemplateResponse(request, "reset_password.html", {"token": token})


@router.get("/trips")
def trips_page(request: Request, user: User | None = Depends(get_current_user_optional)):
    if user is None:
        return RedirectResponse(url="/login")
    return templates.TemplateResponse(request, "trips.html", {})


@router.get("/trips/new")
def trip_new_page(request: Request, user: User | None = Depends(get_current_user_optional)):
    if user is None:
        return RedirectResponse(url="/login")
    return templates.TemplateResponse(request, "trip_form.html", {})


@router.get("/trips/{trip_id}")
def trip_detail_page(
    request: Request,
    trip_id: int,
    user: User | None = Depends(get_current_user_optional),
):
    if user is None:
        return RedirectResponse(url="/login")

    settings = get_settings()

    return templates.TemplateResponse(
        request,
        "trip_detail.html",
        {
            "trip_id": trip_id,
            "google_maps_browser_api_key": settings.google_maps_browser_api_key,
        },
    )


@router.get("/trips/{trip_id}/members")
def trip_members_page(
    request: Request,
    trip_id: int,
    user: User | None = Depends(get_current_user_optional),
):
    if user is None:
        return RedirectResponse(url="/login")
    return templates.TemplateResponse(request, "members.html", {"trip_id": trip_id})


@router.get("/invitations/{token}")
def invitation_accept_page(
    request: Request,
    token: str,
    user: User | None = Depends(get_current_user_optional),
):
    if user is None:
        return RedirectResponse(url=f"/login?next=/invitations/{token}")
    return templates.TemplateResponse(request, "invitation_accept.html", {"token": token})
