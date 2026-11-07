from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_RESERVATION_ANALYSIS_MODEL = "gemini_flash_lite"
RESERVATION_ANALYSIS_MODEL_NAMES = {
    "gemini_flash_lite": "gemini-3.5-flash-lite",
    "gemini_flash": "gemini-3.8-flash",
}


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

    # 지도/장소/AI API 설정
    google_maps_api_key: str = ""
    google_maps_browser_api_key: str = ""
    kakao_rest_api_key: str = ""
    kakao_javascript_key: str = ""
    kakao_javascript_api_key: str = ""
    kakao_maps_browser_api_key: str = ""
    kakao_map_api_key: str = ""
    gemini_api_key: str = ""

    @property
    def resolved_kakao_javascript_key(self) -> str:
        for candidate in (
            self.kakao_javascript_key,
            self.kakao_javascript_api_key,
            self.kakao_maps_browser_api_key,
            self.kakao_map_api_key,
        ):
            cleaned = (candidate or "").strip()
            if cleaned:
                return cleaned
        return ""

@lru_cache
def get_settings() -> Settings:
    return Settings()
