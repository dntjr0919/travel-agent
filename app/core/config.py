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


@lru_cache
def get_settings() -> Settings:
    return Settings()
