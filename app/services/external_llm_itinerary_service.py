from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from app.core.errors import AppError
from app.models.trip import Trip

GOOGLE_MAPS_HOSTS = frozenset(
    {
        "google.com",
        "www.google.com",
        "maps.google.com",
        "goo.gl",
        "maps.app.goo.gl",
    }
)
KAKAO_MAPS_HOSTS: frozenset[str] = frozenset()
NAVER_MAPS_HOSTS: frozenset[str] = frozenset()
MAP_URL_ALLOWED_HOSTS = {
    "google": GOOGLE_MAPS_HOSTS,
    # TODO: Add provider-reviewed Kakao hosts before enabling Kakao map links.
    "kakao": KAKAO_MAPS_HOSTS,
    # TODO: Add provider-reviewed Naver hosts before enabling Naver map links.
    "naver": NAVER_MAPS_HOSTS,
}

_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TIME_PATTERN = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")
_CODE_FENCE_PATTERN = re.compile(r"\A\s*```(?:json)?\s*(.*?)\s*```\s*\Z", re.IGNORECASE | re.DOTALL)
_CODE_FENCE_BLOCK_PATTERN = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.IGNORECASE | re.DOTALL)


class ExternalLlmDraftItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: str
    start_time: str
    end_time: str | None = None
    title: str = Field(min_length=1, max_length=120)
    memo: str = Field(default="", max_length=2000)
    place_name: str = Field(default="", max_length=200)
    place_url: str = ""

    @field_validator("date")
    @classmethod
    def validate_date(cls, value: str) -> str:
        if not _DATE_PATTERN.fullmatch(value):
            raise ValueError("INVALID_DATE_FORMAT")
        try:
            parsed = date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("INVALID_DATE_FORMAT") from exc
        if parsed.isoformat() != value:
            raise ValueError("INVALID_DATE_FORMAT")
        return value

    @field_validator("start_time", "end_time")
    @classmethod
    def validate_time(cls, value: str | None, info) -> str | None:
        if value is None and info.field_name == "end_time":
            return None
        if not isinstance(value, str) or not _TIME_PATTERN.fullmatch(value):
            raise ValueError("INVALID_TIME_FORMAT")
        return value

    @field_validator("title", mode="before")
    @classmethod
    def trim_title(cls, value: Any) -> Any:
        return value.strip() if isinstance(value, str) else value

    @field_validator("end_time", mode="before")
    @classmethod
    def reject_null_end_time(cls, value: Any) -> Any:
        if value is None:
            raise ValueError("INVALID_TIME_FORMAT")
        return value

    @field_validator("place_url")
    @classmethod
    def validate_google_maps_url(cls, value: str) -> str:
        if value == "":
            return value
        if not is_allowed_map_url(value, provider="google"):
            raise ValueError("INVALID_PLACE_URL")
        return value


@dataclass(frozen=True)
class ExternalLlmDraftItemResult:
    index: int
    date: date | None
    title: str
    valid: bool
    error: str | None
    start_at: datetime | None = None
    end_at: datetime | None = None
    location_name: str | None = None
    memo: str | None = None


def is_allowed_map_url(value: str, provider: str = "google") -> bool:
    if not isinstance(value, str) or not value or value != value.strip():
        return False
    try:
        parsed = urlsplit(value)
        hostname = parsed.hostname
        port = parsed.port
    except ValueError:
        return False
    if (
        parsed.scheme.lower() != "https"
        or hostname is None
        or parsed.username is not None
        or parsed.password is not None
        or port not in (None, 443)
    ):
        return False
    return hostname.lower() in MAP_URL_ALLOWED_HOSTS.get(provider, frozenset())


def _raise_invalid_json(message: str) -> None:
    raise AppError(422, "EXTERNAL_LLM_INVALID_JSON", message)


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"Invalid JSON constant: {value}")


def extract_json_object_text(raw_text: str) -> str:
    """외부 LLM 출력 문자열에서 JSON 객체({...}) 부분만 추출한다."""
    content = raw_text.strip()
    if not content:
        return content

    # 1. 전체 문자열이 유효한 JSON 객체({...})인지 확인
    if content.startswith("{") and content.endswith("}"):
        try:
            parsed = json.loads(content, parse_constant=_reject_json_constant)
            if isinstance(parsed, dict):
                return content
        except (json.JSONDecodeError, ValueError, RecursionError):
            pass

    # 2. 마크다운 코드 블록(```json ... ``` 또는 ``` ... ```) 내부 탐색
    fallback_dict_text: str | None = None
    for match in _CODE_FENCE_BLOCK_PATTERN.finditer(content):
        block = match.group(1).strip()
        if not block:
            continue
        try:
            parsed = json.loads(block, parse_constant=_reject_json_constant)
            if isinstance(parsed, dict):
                if "items" in parsed:
                    return block
                if fallback_dict_text is None:
                    fallback_dict_text = block
        except (json.JSONDecodeError, ValueError, RecursionError):
            pass

    if fallback_dict_text is not None:
        return fallback_dict_text

    # 3. 일반 텍스트 중간에 삽입된 balanced JSON 객체({...}) 스캔
    decoder = json.JSONDecoder(parse_constant=_reject_json_constant)
    search_pos = 0
    while True:
        brace_idx = content.find("{", search_pos)
        if brace_idx == -1:
            break
        try:
            parsed, end_idx = decoder.raw_decode(content, brace_idx)
            if isinstance(parsed, dict):
                candidate_text = content[brace_idx:end_idx]
                if "items" in parsed:
                    return candidate_text
                if fallback_dict_text is None:
                    fallback_dict_text = candidate_text
                search_pos = end_idx
                continue
        except (json.JSONDecodeError, ValueError, RecursionError):
            pass
        search_pos = brace_idx + 1

    if fallback_dict_text is not None:
        return fallback_dict_text

    fenced = _CODE_FENCE_PATTERN.fullmatch(content)
    if fenced:
        return fenced.group(1).strip()
    return content


def _validation_message(error: ValidationError) -> str:
    errors = error.errors(include_url=False)
    if any(item["type"] == "extra_forbidden" for item in errors):
        return "지원하지 않는 필드가 포함되어 있습니다."
    field = str(errors[0].get("loc", ("",))[0]) if errors else ""
    messages = {
        "date": "날짜는 YYYY-MM-DD 형식으로 입력하세요.",
        "start_time": "시작 시간은 24시간 HH:MM 형식으로 입력하세요.",
        "end_time": "종료 시간은 24시간 HH:MM 형식으로 입력하세요.",
        "title": "일정 제목은 공백 제외 1~120자로 입력하세요.",
        "memo": "메모는 2000자 이하여야 합니다.",
        "place_name": "장소명은 200자 이하여야 합니다.",
        "place_url": "장소 링크는 HTTPS Google 지도 URL만 사용할 수 있습니다.",
    }
    if errors and errors[0]["type"] == "missing":
        return {
            "date": "날짜를 입력하세요.",
            "start_time": "시작 시간을 입력하세요.",
            "title": "일정 제목을 입력하세요.",
        }.get(field, "필수 항목이 누락되었습니다.")
    return messages.get(field, "항목 형식이 올바르지 않습니다.")


def _trip_timezone(trip: Trip) -> ZoneInfo:
    try:
        return ZoneInfo(trip.timezone or "Asia/Seoul")
    except Exception:
        raise AppError(
            422,
            "EXTERNAL_LLM_INVALID_TIMEZONE",
            "여행 시간대 설정이 올바르지 않습니다. 예: Asia/Tokyo",
        ) from None


def parse_external_llm_draft(raw_json: str, trip: Trip) -> list[ExternalLlmDraftItemResult]:
    try:
        encoded = raw_json.encode("utf-8")
    except UnicodeEncodeError:
        _raise_invalid_json("JSON 입력을 UTF-8로 처리할 수 없습니다.")
    if len(encoded) > 100 * 1024:
        _raise_invalid_json("JSON 입력은 UTF-8 기준 100KB 이하여야 합니다.")
    if not raw_json.strip():
        _raise_invalid_json("JSON을 붙여넣으세요.")

    content = extract_json_object_text(raw_json)
    try:
        document = json.loads(content, parse_constant=_reject_json_constant)
    except (json.JSONDecodeError, ValueError, RecursionError):
        _raise_invalid_json("JSON 형식을 확인하세요.")

    if not isinstance(document, dict) or set(document) != {"version", "items"}:
        _raise_invalid_json("최상위 객체는 version과 items만 포함해야 합니다.")
    if type(document["version"]) is not int or document["version"] != 1:
        _raise_invalid_json("version은 숫자 1이어야 합니다.")
    raw_items = document["items"]
    if not isinstance(raw_items, list) or not 1 <= len(raw_items) <= 30:
        _raise_invalid_json("items는 1개 이상 30개 이하의 배열이어야 합니다.")

    results: list[ExternalLlmDraftItemResult] = []
    trip_timezone = _trip_timezone(trip)
    allowed_fields = set(ExternalLlmDraftItem.model_fields)

    for index, raw_item in enumerate(raw_items):
        preview_title = raw_item.get("title", "") if isinstance(raw_item, dict) else ""
        preview_title = preview_title.strip()[:120] if isinstance(preview_title, str) else ""
        preview_date = raw_item.get("date") if isinstance(raw_item, dict) else None
        parsed_date = None
        if isinstance(preview_date, str) and _DATE_PATTERN.fullmatch(preview_date):
            try:
                parsed_date = date.fromisoformat(preview_date)
                if parsed_date.isoformat() != preview_date:
                    parsed_date = None
            except ValueError:
                parsed_date = None

        if not isinstance(raw_item, dict):
            results.append(ExternalLlmDraftItemResult(index, parsed_date, preview_title, False, "일정 항목은 객체여야 합니다."))
            continue
        unknown_fields = sorted(set(raw_item) - allowed_fields)
        if unknown_fields:
            results.append(ExternalLlmDraftItemResult(index, parsed_date, preview_title, False, "지원하지 않는 필드: " + ", ".join(unknown_fields[:3])))
            continue
        try:
            item = ExternalLlmDraftItem.model_validate(raw_item)
        except ValidationError as exc:
            results.append(ExternalLlmDraftItemResult(index, parsed_date, preview_title, False, _validation_message(exc)))
            continue

        item_date = date.fromisoformat(item.date)
        if item_date < trip.start_date or item_date > trip.end_date:
            results.append(ExternalLlmDraftItemResult(index, item_date, item.title, False, "여행 기간을 벗어난 날짜입니다."))
            continue

        start_time = time.fromisoformat(item.start_time)
        start_at = datetime.combine(item_date, start_time, tzinfo=trip_timezone)
        end_time = time.fromisoformat(item.end_time) if item.end_time else None
        end_at = datetime.combine(item_date, end_time, tzinfo=trip_timezone) if end_time else start_at + timedelta(hours=1)
        if end_at <= start_at:
            results.append(ExternalLlmDraftItemResult(index, item_date, item.title, False, "종료 시간은 시작 시간보다 늦어야 합니다."))
            continue
        if end_at.astimezone(trip_timezone).date() > trip.end_date:
            results.append(ExternalLlmDraftItemResult(index, item_date, item.title, False, "종료 시각이 여행 기간을 벗어납니다."))
            continue

        memo_parts = [part for part in (item.memo, f"지도: {item.place_url}" if item.place_url else "") if part]
        results.append(
            ExternalLlmDraftItemResult(
                index=index,
                date=item_date,
                title=item.title,
                valid=True,
                error=None,
                start_at=start_at,
                end_at=end_at,
                location_name=item.place_name or None,
                memo="\n".join(memo_parts) or None,
            )
        )

    return results
