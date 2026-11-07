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

MAX_EXTERNAL_LLM_ITEMS = 200

GOOGLE_MAPS_HOSTS = frozenset(
    {
        "google.com",
        "www.google.com",
        "maps.google.com",
        "goo.gl",
        "maps.app.goo.gl",
    }
)
KAKAO_MAPS_HOSTS = frozenset(
    {
        "map.kakao.com",
        "place.map.kakao.com",
        "kko.to",
        "m.map.kakao.com",
    }
)
NAVER_MAPS_HOSTS = frozenset(
    {
        "map.naver.com",
        "m.map.naver.com",
        "naver.me",
    }
)
MAP_URL_ALLOWED_HOSTS = {
    "google": GOOGLE_MAPS_HOSTS,
    "kakao": KAKAO_MAPS_HOSTS,
    "naver": NAVER_MAPS_HOSTS,
    "any": GOOGLE_MAPS_HOSTS | KAKAO_MAPS_HOSTS | NAVER_MAPS_HOSTS,
}

_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TIME_PATTERN = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")
_SINGLE_HOUR_TIME_PATTERN = re.compile(r"^(\d):([0-5]\d)$")
_CODE_FENCE_PATTERN = re.compile(
    r"\A\s*```(?:json|jsonc|javascript|js|ts|plaintext|text)?\b[ \t]*\r?\n?(.*?)\r?\n?```\s*\Z",
    re.IGNORECASE | re.DOTALL,
)
_CODE_FENCE_BLOCK_PATTERN = re.compile(
    r"```(?:json|jsonc|javascript|js|ts|plaintext|text)?\b[ \t]*(.*?)\s*```",
    re.IGNORECASE | re.DOTALL,
)
_LEADING_CODE_FENCE_PATTERN = re.compile(
    r"\A\s*```(?:json|jsonc|javascript|js|ts|plaintext|text)?\b[ \t]*\r?\n?",
    re.IGNORECASE,
)
_MULTILINE_JSON_BLOCK_PATTERN = re.compile(r"(\{[\s\S]*\}|\[[\s\S]*\])", re.DOTALL)
_ZERO_WIDTH_PATTERN = re.compile(r"[\u200b\u200c\u200d\ufeff]")
_CITATION_FOOTER_PATTERN = re.compile(r"(?:\n\s*|\A\s*)(?:citations|출처|references)\s*:[\s\S]*\Z", re.IGNORECASE)
_BRACE_CITATION_PATTERN = re.compile(r"([\}\]])\s*(?:\[\d+\])+")
_QUOTE_CITATION_PATTERN = re.compile(r'"\s*(?:\[\d+\])+\s*(?=[,\}\]:])')
_PRE_PUNCT_CITATION_PATTERN = re.compile(r"(?:\[\d+\])+\s*([,\}\]])")
_INLINE_CITATION_PATTERN = re.compile(r"(?:\s*\[\d+\])+")
_PERPLEXITY_CITATION_PATTERN = re.compile(r"【\d+(?::\d+)?†(?:source|출처)】")
_SMART_QUOTE_PATTERN = re.compile(r'[\u201c\u201d\u201e\u2033]')
_TRAILING_COMMA_PATTERN = re.compile(r",\s*([\}\]])")
_PREFERRED_CONTAINER_KEYS = frozenset(
    {
        "items",
        "days",
        "daily_schedule",
        "itinerary_days",
        "itineraries",
        "itinerary",
        "schedule",
        "schedules",
        "events",
        "plans",
        "plan",
        "data",
        "activities",
    }
)


def _strip_citations_and_zero_width(value: str) -> str:
    cleaned = _ZERO_WIDTH_PATTERN.sub("", value)
    cleaned = cleaned.replace("\u00a0", " ")
    cleaned = _PERPLEXITY_CITATION_PATTERN.sub("", cleaned)
    cleaned = _INLINE_CITATION_PATTERN.sub("", cleaned)
    return cleaned.strip()


def _escape_literal_control_chars_in_strings(raw_text: str) -> str:
    if "\n" not in raw_text and "\r" not in raw_text and "\t" not in raw_text:
        return raw_text
    out: list[str] = []
    in_string = False
    escaped = False
    for ch in raw_text:
        if in_string:
            if escaped:
                escaped = False
                out.append(ch)
            elif ch == "\\":
                escaped = True
                out.append(ch)
            elif ch == '"':
                in_string = False
                out.append(ch)
            elif ch == "\n":
                out.append("\\n")
            elif ch == "\r":
                out.append("\\r")
            elif ch == "\t":
                out.append("\\t")
            else:
                out.append(ch)
        else:
            if ch == '"':
                in_string = True
            out.append(ch)
    return "".join(out)


def _strip_outer_code_fence(raw_text: str) -> str:
    trimmed = raw_text.strip()
    fenced = _CODE_FENCE_PATTERN.fullmatch(trimmed)
    if fenced and "```" not in fenced.group(1):
        return fenced.group(1).strip()
    if _LEADING_CODE_FENCE_PATTERN.match(trimmed) and "```" not in trimmed[3:]:
        return _LEADING_CODE_FENCE_PATTERN.sub("", trimmed, count=1).strip()
    if trimmed.endswith("```") and "```" not in trimmed[:-3]:
        return trimmed[:-3].strip()
    return trimmed


def _clean_llm_json_source(raw_text: str, *, replace_smart_quotes: bool = True) -> str:
    cleaned = _ZERO_WIDTH_PATTERN.sub("", raw_text).replace("\r\n", "\n").replace("\r", "\n").strip()
    if not cleaned:
        return cleaned
    # 마크다운 이스케이프 문자(\_, \[, \], \{, \}) 복구
    cleaned = re.sub(r"\\([_\[\]{}])", r"\1", cleaned)
    cleaned = cleaned.replace("\u00a0", " ")
    if replace_smart_quotes:
        cleaned = _SMART_QUOTE_PATTERN.sub('"', cleaned)
    cleaned = _CITATION_FOOTER_PATTERN.sub("", cleaned).strip()
    cleaned = _PERPLEXITY_CITATION_PATTERN.sub("", cleaned)
    cleaned = _BRACE_CITATION_PATTERN.sub(r"\1", cleaned)
    cleaned = _QUOTE_CITATION_PATTERN.sub('"', cleaned)
    cleaned = _PRE_PUNCT_CITATION_PATTERN.sub(r"\1", cleaned)
    cleaned = _TRAILING_COMMA_PATTERN.sub(r"\1", cleaned)
    return cleaned.strip()


class ExternalLlmDraftItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: str
    start_time: str
    end_time: str | None = None
    title: str = Field(min_length=1, max_length=120)
    memo: str = Field(default="", max_length=2000)
    place_name: str = Field(default="", max_length=200)
    place_url: str = ""

    @field_validator("date", mode="before")
    @classmethod
    def clean_date(cls, value: Any) -> Any:
        if isinstance(value, str):
            return _strip_citations_and_zero_width(value)
        return value

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

    @field_validator("start_time", "end_time", mode="before")
    @classmethod
    def normalize_time_input(cls, value: Any, info) -> Any:
        if info.field_name == "end_time" and (value is None or (isinstance(value, str) and not _strip_citations_and_zero_width(value))):
            return None
        if isinstance(value, str):
            cleaned = _strip_citations_and_zero_width(value)
            single_match = _SINGLE_HOUR_TIME_PATTERN.fullmatch(cleaned)
            if single_match:
                return f"0{single_match.group(1)}:{single_match.group(2)}"
            return cleaned
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
        return _strip_citations_and_zero_width(value) if isinstance(value, str) else value

    @field_validator("memo", "place_name", mode="before")
    @classmethod
    def clean_optional_text(cls, value: Any) -> Any:
        if value is None:
            return ""
        if isinstance(value, str):
            return _strip_citations_and_zero_width(value)
        return value

    @field_validator("place_url", mode="before")
    @classmethod
    def clean_place_url(cls, value: Any) -> Any:
        if value is None:
            return ""
        if isinstance(value, str):
            cleaned = _strip_citations_and_zero_width(value)
            if cleaned.startswith("https://") and " " in cleaned:
                cleaned = re.sub(r"\s+", "%20", cleaned)
            return cleaned
        return value

    @field_validator("place_url")
    @classmethod
    def validate_place_url(cls, value: str) -> str:
        if value == "":
            return value
        if not is_allowed_map_url(value, provider="any"):
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
    place_url: str | None = None


def is_allowed_map_url(value: str, provider: str = "any") -> bool:
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
    allowed = MAP_URL_ALLOWED_HOSTS.get(provider, MAP_URL_ALLOWED_HOSTS["any"])
    return hostname.lower() in allowed


def _raise_invalid_json(message: str) -> None:
    raise AppError(422, "EXTERNAL_LLM_INVALID_JSON", message)


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"Invalid JSON constant: {value}")


def _wrap_array_if_dict_items(parsed: Any) -> str | None:
    """최상위 배열의 항목들이 모두 dict인 경우 {"version": 1, "items": [...]}로 감싸 JSON 문자열로 반환한다."""
    if isinstance(parsed, list) and len(parsed) > 0 and all(isinstance(item, dict) for item in parsed):
        return json.dumps({"version": 1, "items": parsed}, ensure_ascii=False)
    return None


def _try_parse_json_candidate(candidate_text: str) -> tuple[dict[str, Any], str] | None:
    base = _strip_outer_code_fence(candidate_text)
    if not base:
        return None
    variants = [
        _clean_llm_json_source(base, replace_smart_quotes=False),
        _clean_llm_json_source(base, replace_smart_quotes=True),
        _escape_literal_control_chars_in_strings(_clean_llm_json_source(base, replace_smart_quotes=False)),
        _escape_literal_control_chars_in_strings(_clean_llm_json_source(base, replace_smart_quotes=True)),
    ]
    seen: set[str] = set()
    for variant in variants:
        if not variant or variant in seen:
            continue
        seen.add(variant)
        try:
            parsed = json.loads(variant, parse_constant=_reject_json_constant)
            if isinstance(parsed, dict):
                return parsed, variant
            wrapped = _wrap_array_if_dict_items(parsed)
            if wrapped is not None:
                return json.loads(wrapped), wrapped
        except RecursionError:
            raise
        except (json.JSONDecodeError, ValueError):
            pass
    return None


def _is_preferred_itinerary_dict(parsed: dict[str, Any]) -> bool:
    return any(key in parsed for key in _PREFERRED_CONTAINER_KEYS)


def extract_json_object_text(raw_text: str) -> str:
    """외부 LLM 출력 문자열에서 JSON 객체({...}) 또는 배열([{"date":...}])을 감지해 추출한다."""
    content = _clean_llm_json_source(raw_text)
    if not content:
        return content

    try:
        # 1. 양끝 마크다운 코드블록(```json ... ```) 제거 후 전체 문자열이 유효한 JSON 객체/배열인지 확인
        stripped_outer = _strip_outer_code_fence(raw_text)
        cleaned_outer = _clean_llm_json_source(stripped_outer)
        if (cleaned_outer.startswith("{") and cleaned_outer.endswith("}")) or (
            cleaned_outer.startswith("[") and cleaned_outer.endswith("]")
        ):
            direct = _try_parse_json_candidate(stripped_outer)
            if direct is not None:
                return direct[1]

        # 2. 마크다운 코드 블록(```json ... ``` 또는 ``` ... ```) 내부 다중 줄 탐색
        fallback_dict_text: str | None = None
        for match in _CODE_FENCE_BLOCK_PATTERN.finditer(raw_text):
            block_result = _try_parse_json_candidate(match.group(1))
            if block_result is not None:
                parsed_dict, normalized_text = block_result
                if _is_preferred_itinerary_dict(parsed_dict):
                    return normalized_text
                if fallback_dict_text is None:
                    fallback_dict_text = normalized_text

        if fallback_dict_text is not None:
            return fallback_dict_text

        # 3. 일반 텍스트 중간에 삽입된 다중 줄 balanced JSON 객체({...}) 또는 배열([...]) 스캔
        decoder = json.JSONDecoder(parse_constant=_reject_json_constant)
        scan_sources = [content]
        escaped_content = _escape_literal_control_chars_in_strings(content)
        if escaped_content != content:
            scan_sources.append(escaped_content)

        for scan_source in scan_sources:
            search_pos = 0
            while search_pos < len(scan_source):
                brace_idx = scan_source.find("{", search_pos)
                bracket_idx = scan_source.find("[", search_pos)
                if brace_idx != -1 and bracket_idx != -1:
                    start_idx = min(brace_idx, bracket_idx)
                else:
                    start_idx = brace_idx if brace_idx != -1 else bracket_idx
                if start_idx == -1:
                    break
                try:
                    parsed, end_idx = decoder.raw_decode(scan_source, start_idx)
                    if isinstance(parsed, dict):
                        candidate_text = scan_source[start_idx:end_idx]
                        if _is_preferred_itinerary_dict(parsed):
                            return candidate_text
                        if fallback_dict_text is None:
                            fallback_dict_text = candidate_text
                        search_pos = end_idx
                        continue
                    wrapped = _wrap_array_if_dict_items(parsed)
                    if wrapped is not None:
                        return wrapped
                except RecursionError:
                    raise
                except (json.JSONDecodeError, ValueError):
                    pass
                search_pos = start_idx + 1

        if fallback_dict_text is not None:
            return fallback_dict_text

        # 4. 다중 줄 정규식(re.DOTALL) 기반 최외곽 { ... } 또는 [ ... ] 블록 추출 시도
        multiline_match = _MULTILINE_JSON_BLOCK_PATTERN.search(stripped_outer)
        if multiline_match:
            block_result = _try_parse_json_candidate(multiline_match.group(1))
            if block_result is not None:
                return block_result[1]
    except RecursionError:
        return content

    fenced = _CODE_FENCE_PATTERN.fullmatch(content)
    if fenced:
        return _clean_llm_json_source(fenced.group(1))
    return _strip_outer_code_fence(content)


def _parse_time_string(val: str) -> str | None:
    """다양한 시간 형식("09:00", "9시", "오전 9:30", "오후 2:00", "14:00:00")을 HH:MM으로 정규화한다."""
    if not isinstance(val, str):
        return None
    s = _strip_citations_and_zero_width(val).strip()
    if not s:
        return None

    # 초 단위 제거 (예: "09:00:00" -> "09:00")
    sec_match = re.fullmatch(r"(\d{1,2}):(\d{2}):\d{2}", s)
    if sec_match:
        h, m = int(sec_match.group(1)), int(sec_match.group(2))
        if 0 <= h <= 23 and 0 <= m <= 59:
            return f"{h:02d}:{m:02d}"

    # 기본 HH:MM
    if _TIME_PATTERN.fullmatch(s):
        return s
    single_match = _SINGLE_HOUR_TIME_PATTERN.fullmatch(s)
    if single_match:
        return f"0{single_match.group(1)}:{single_match.group(2)}"

    # "오전/오후" 또는 "AM/PM" 형식
    ampm_match = re.search(r"(오전|오후|AM|PM)\s*(\d{1,2})(?::(\d{2}))?", s, re.IGNORECASE)
    if ampm_match:
        is_pm = ampm_match.group(1).upper() in ("오후", "PM")
        hour = int(ampm_match.group(2))
        minute = int(ampm_match.group(3) or 0)
        if is_pm and hour < 12:
            hour += 12
        elif not is_pm and hour == 12:
            hour = 0
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return f"{hour:02d}:{minute:02d}"

    # "9시", "14시 30분" 형식
    kr_match = re.search(r"(\d{1,2})\s*시(?:\s*(\d{1,2})\s*분)?", s)
    if kr_match:
        hour = int(kr_match.group(1))
        minute = int(kr_match.group(2) or 0)
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return f"{hour:02d}:{minute:02d}"

    return None


def _normalize_llm_payload_dict(document: dict[str, Any], trip: Trip) -> dict[str, Any]:
    """다양한 LLM 출력 형태(컨테이너 키, days 그룹, 별칭 키 등)를 표준 version=1, items=[...]로 변환한다."""
    if not isinstance(document, dict):
        return document

    raw_items = document.get("items")
    # 1. 대체 컨테이너 키 탐색
    if raw_items is None or not isinstance(raw_items, list):
        for alt_key in ("itineraries", "itinerary", "schedule", "schedules", "events", "plans", "plan", "data", "activities"):
            val = document.get(alt_key)
            if isinstance(val, list):
                raw_items = val
                break

    # 2. days / daily_schedule 중첩 구조 평탄화
    if raw_items is None or not isinstance(raw_items, list):
        for days_key in ("days", "daily_schedule", "itinerary_days"):
            days_val = document.get(days_key)
            if isinstance(days_val, list):
                flattened = []
                for day_group in days_val:
                    if not isinstance(day_group, dict):
                        continue
                    day_date = day_group.get("date") or day_group.get("day") or day_group.get("day_date")
                    sub_items = None
                    for sub_key in ("items", "activities", "schedule", "places", "plans", "events"):
                        if isinstance(day_group.get(sub_key), list):
                            sub_items = day_group[sub_key]
                            break
                    if sub_items is not None:
                        for sub_item in sub_items:
                            if isinstance(sub_item, dict):
                                if "date" not in sub_item and day_date:
                                    sub_item["date"] = day_date
                                flattened.append(sub_item)
                raw_items = flattened
                break

    if raw_items is None or not isinstance(raw_items, list):
        return document

    # 3. 항목별 필드명 별칭(Alias) 자동 매핑 및 포맷 보정
    normalized_items: list[Any] = []
    prev_time_by_date: dict[str, str] = {}

    for idx, raw_item in enumerate(raw_items):
        if not isinstance(raw_item, dict):
            normalized_items.append(raw_item)
            continue

        item = dict(raw_item)

        # date 매핑
        raw_date = None
        for k in ("date", "day_date", "travel_date", "start_date"):
            if k in item and item[k] is not None:
                raw_date = str(item.pop(k)).strip()
                break

        if raw_date:
            raw_date = _strip_citations_and_zero_width(raw_date)
            dot_or_slash = re.fullmatch(r"(\d{4})[./](\d{1,2})[./](\d{1,2})", raw_date)
            if dot_or_slash:
                raw_date = f"{int(dot_or_slash.group(1)):04d}-{int(dot_or_slash.group(2)):02d}-{int(dot_or_slash.group(3)):02d}"
            else:
                day_match = re.search(r"(?:day\s*|)(\d+)\s*(?:일차|일)?", raw_date, re.IGNORECASE)
                if day_match and not _DATE_PATTERN.fullmatch(raw_date):
                    try:
                        day_num = int(day_match.group(1))
                        if day_num >= 1 and trip.start_date:
                            calc_date = trip.start_date + timedelta(days=day_num - 1)
                            raw_date = calc_date.isoformat()
                    except (ValueError, TypeError):
                        pass
            item["date"] = raw_date

        # title 매핑
        raw_title = None
        for k in ("title", "name", "activity", "event", "summary"):
            if k in item and item[k] is not None:
                raw_title = str(item.pop(k)).strip()
                break
        if raw_title is None and "place_name" in item and item["place_name"] and "location" not in item:
            raw_title = str(item["place_name"]).strip()
        elif raw_title is None and "location" in item and item["location"] and "place_name" not in item:
            raw_title = str(item["location"]).strip()

        if raw_title is not None:
            raw_title = _strip_citations_and_zero_width(raw_title)
            item["title"] = raw_title[:120] if raw_title else "일정"

        # time 매핑 (start_time / end_time)
        raw_start = None
        for k in ("start_time", "startTime", "time", "start", "begin_time"):
            if k in item and item[k] is not None:
                raw_start = str(item.pop(k)).strip()
                break

        raw_end = None
        for k in ("end_time", "endTime", "end", "finish_time"):
            if k in item and item[k] is not None:
                raw_end = str(item.pop(k)).strip()
                break

        # start_time에 "09:00 - 10:30" 또는 "09:00~11:00"처럼 범위가 있는 경우 분리
        if raw_start and ("-" in raw_start or "~" in raw_start):
            sep = "-" if "-" in raw_start else "~"
            parts = raw_start.split(sep, 1)
            raw_start = parts[0].strip()
            if not raw_end:
                raw_end = parts[1].strip()

        parsed_start = _parse_time_string(raw_start) if raw_start else None
        parsed_end = _parse_time_string(raw_end) if raw_end else None

        current_date_key = item.get("date", "")
        if raw_start is None:
            # start_time 필드가 아예 없었던 경우에만 자동 채움
            if current_date_key in prev_time_by_date:
                prev_hour = int(prev_time_by_date[current_date_key].split(":")[0])
                next_hour = min(prev_hour + 1, 23)
                parsed_start = f"{next_hour:02d}:00"
            else:
                parsed_start = "09:00"

        if parsed_start:
            item["start_time"] = parsed_start
            prev_time_by_date[current_date_key] = parsed_start
        elif raw_start is not None:
            item["start_time"] = raw_start

        if parsed_end:
            if parsed_start and parsed_end <= parsed_start:
                item["end_time"] = None
            else:
                item["end_time"] = parsed_end
        elif raw_end is not None:
            item["end_time"] = raw_end

        # place_name 매핑
        raw_place = None
        for k in ("place_name", "placeName", "location_name", "location", "place", "spot", "address"):
            if k in item and item[k] is not None:
                raw_place = str(item.pop(k)).strip()
                break
        if raw_place is not None:
            raw_place = _strip_citations_and_zero_width(raw_place)
            item["place_name"] = raw_place[:200]

        # memo 매핑
        raw_memo = None
        for k in ("memo", "description", "notes", "note", "detail", "details", "reason", "tip"):
            if k in item and item[k] is not None:
                raw_memo = str(item.pop(k)).strip()
                break
        if raw_memo is not None:
            raw_memo = _strip_citations_and_zero_width(raw_memo)
            item["memo"] = raw_memo[:2000]

        # place_url 매핑
        raw_url = None
        for k in ("place_url", "placeUrl", "map_url", "mapUrl", "url", "link", "google_maps_url", "kakao_map_url"):
            if k in item and item[k] is not None:
                raw_url = str(item.pop(k)).strip()
                break
        if raw_url is not None:
            raw_url = _strip_citations_and_zero_width(raw_url)
            item["place_url"] = raw_url

        normalized_items.append(item)

    return {"version": 1, "items": normalized_items}


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
        "place_url": "장소 링크는 HTTPS Google, Kakao, Naver 지도 URL만 사용할 수 있습니다.",
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

    if isinstance(document, list):
        wrapped = _wrap_array_if_dict_items(document)
        if wrapped is not None:
            document = json.loads(wrapped)

    if not isinstance(document, dict):
        _raise_invalid_json("최상위 객체는 version과 items만 포함해야 합니다.")

    # 다양한 스키마/별칭/중첩 구조 자동 정규화
    document = _normalize_llm_payload_dict(document, trip)

    if not isinstance(document, dict) or set(document) != {"version", "items"}:
        _raise_invalid_json("최상위 객체는 version과 items만 포함해야 합니다.")
    if type(document["version"]) is not int or document["version"] != 1:
        _raise_invalid_json("version은 숫자 1이어야 합니다.")
    raw_items = document["items"]
    if not isinstance(raw_items, list) or len(raw_items) < 1:
        _raise_invalid_json("items는 1개 이상 200개 이하의 배열이어야 합니다.")
    if len(raw_items) > MAX_EXTERNAL_LLM_ITEMS:
        _raise_invalid_json("일정은 한 번에 최대 200개까지 분석할 수 있습니다.")

    results: list[ExternalLlmDraftItemResult] = []
    trip_timezone = _trip_timezone(trip)
    allowed_fields = set(ExternalLlmDraftItem.model_fields)

    for index, raw_item in enumerate(raw_items):
        preview_title = raw_item.get("title", "") if isinstance(raw_item, dict) else ""
        preview_title = _strip_citations_and_zero_width(preview_title)[:120] if isinstance(preview_title, str) else ""
        preview_date = raw_item.get("date") if isinstance(raw_item, dict) else None
        if isinstance(preview_date, str):
            preview_date = _strip_citations_and_zero_width(preview_date)
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
                place_url=item.place_url or None,
            )
        )

    return results
