from __future__ import annotations

import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """환경변수 기반 설정. .env 파일에서 값을 읽는다."""

    database_url: str = "sqlite:///./travel_planner.db"
    secret_key: str = "dev-only-insecure-secret-key"
    session_max_age_seconds: int = 604800
    invitation_expire_hours: int = 168
    password_reset_expire_minutes: int = 30
    app_base_url: str = "http://127.0.0.1:8000"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    # SMTP 이메일 발송 설정
    email_enabled: bool = False
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""
    smtp_from_name: str = "Travel Planner"
    smtp_use_tls: bool = True
        # 장소 검색 API 설정
    google_maps_api_key: str = ""
    kakao_rest_api_key: str = ""

@lru_cache
def get_settings() -> Settings:
    return Settings()
