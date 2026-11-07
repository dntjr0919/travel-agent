# Travel Planner 외부 LLM 만능 JSON 파서 및 국내 여행(Kakao 지도/검색) 전환 작업 지시서

아래 프롬프트 전문을 복사하여 코딩 에이전트(Claude Code, Cursor, Windsurf, Copilot 등)에 전달하세요.

---

## 코딩 에이전트 전달용 프롬프트 전문

당신은 이 저장소(FastAPI + SQLAlchemy + Jinja2 + Vanilla JS 기반 `Travel Planner` 웹 앱)를 담당하는 시니어 풀스택 엔지니어입니다.
현재 코드베이스의 기존 기능과 `pytest` 테스트 계약(특히 `tests/test_pages.py` 및 `tests/test_external_llm_itineraries.py`)을 유지하면서, 아래 **2가지 핵심 파트(Part 1: 외부 LLM 만능 JSON 파서 & 개수 제한 해제, Part 2: 국내 여행 `Asia/Seoul` 시 Kakao Maps SDK 연동 및 국내 지도 친화적 UI 전환)**를 구현하세요.

---

## 핵심 제약 조건 (반드시 준수할 것)

1. **기존 테스트 통과 + 변경된 정책에 맞춘 테스트 갱신 및 추가**:
   - `tests/test_pages.py`가 검사하는 인라인 `<script>` 구조 및 함수 위치 계약(`PLACE_CANDIDATE_PAGE_SIZE`, `getPlaceCandidatePage`, `renderPlaceCandidates`, `extractJsonObjectFromLlmText`, `setExternalLlmFeedback`, `reservationImageFileInput`, `initAiItineraryMap`, Google Maps 스크립트 태그 위치 등)을 절대 깨뜨리지 마세요.
   - `tests/test_external_llm_itineraries.py`에서 기존 30개 제한을 검증하던 `test_document_rejects_more_than_thirty_items`와 호스트 목록을 검증하던 `test_provider_host_lists_only_enable_google_for_now`는 아래 명세에 맞게 상한선(200개) 및 Kakao/Naver 허용 정책에 맞추어 업데이트하고, 신규 테스트 케이스를 추가하세요.
2. **DB 스키마 무변경 원칙 (No Alembic Migration)**:
   - 새 테이블이나 컬럼을 추가하지 마세요. 기존 `Trip.timezone`, `ItineraryItem`, `PlaceCandidate` 스키마를 그대로 활용합니다.

---

## Part 1. 외부 LLM 응답 만능 JSON 필터링·정규화 및 30개 제한 해제

모바일 환경에서 ChatGPT, Claude, Gemini, Perplexity 등의 응답을 복사·붙여넣기 할 때 JSON이 깨지거나 부연 설명·인용구가 섞이는 문제를 해결하고, 일정 객체가 30개를 초과하거나 스키마가 조금 달라도 어떤 JSON 응답이든 유연하게 받아들이도록 프론트엔드와 백엔드를 모두 개선하세요.

### 1. 일정 개수 상한 대폭 확대 (30개 -> 200개) 및 용량 상한 확대
- **`app/services/external_llm_itinerary_service.py`**:
  - `MAX_EXTERNAL_LLM_ITEMS`(또는 `parse_external_llm_draft` 내부의 `len(raw_items) > 30` 검사)를 **200개(`200`)**로 확대하세요. (에러 메시지도 `"일정은 한 번에 최대 200개까지 분석할 수 있습니다."`로 변경)
  - UTF-8 바이트 크기 제한이 필요한 경우 기존 `100_000` 바이트(100KB)는 유지하되(기존 `test_document_rejects_utf8_payload_over_100_kb` 통과 보장), 30개 초과 일정(예: 35~100개)이 정상 통과되도록 하세요.
- **`app/schemas/external_llm_itinerary.py`**:
  - `ExternalLlmItineraryImportRequest.selected_indices`의 `Field(min_length=1, max_length=30)`을 `Field(min_length=1, max_length=200)`으로 변경하세요.
- **`app/templates/trip_detail.html`**:
  - `buildExternalLlmPrompt()` 내 `"items는 1~30개입니다."` 문구를 `"items는 여행 일정에 맞게 자유롭게(최대 200개) 구성하세요."`로 수정하세요.

### 2. 모바일 복붙 노이즈 제거 및 깨진 JSON 자동 복구 (`_clean_llm_json_source` & 프론트엔드 `extractJsonObjectFromLlmText`)
백엔드(`app/services/external_llm_itinerary_service.py`)와 프론트엔드(`app/templates/trip_detail.html`) 양쪽의 JSON 추출기를 다음 순서로 동작하도록 강화하세요:
1. **모바일 클립보드 노이즈 정화**:
   - Zero-width 문자(`​`, `‌`, `‍`, `﻿`) 제거 및 Non-breaking space(` `)를 일반 공백(`" "`)으로 치환.
   - 모바일 키보드/앱 복사 시 변환된 유니코드 스마트 큰따옴표(`“`, `”`, `„`, `″`)를 표준 `"`로 치환(단, 문자열 내부가 깨지지 않도록 JSON 키/구분자 패턴 우선 정화).
   - Perplexity/ChatGPT 검색 인용 각주 제거: `[1]`, `[1][2]`, `【1†source】`, `【12:3†출처】`, `
Citations:...`, `
출처:...` 제거.
   - JSON 문법 오류 자동 수리:
     - 객체나 배열 닫는 괄호 직전의 후행 쉼표(Trailing comma: `,\s*([\}\]])` -> ``) 자동 제거.
     - 코드 블록 외곽의 마크다운 강조 표시(`**`)나 리스트 기호 제거.
2. **최상위 JSON 배열(`[...]`) 및 다양한 래퍼 구조 수용**:
   - 사용자가 붙여넣은 JSON의 최상위가 객체(`{...}`)가 아니라 배열(`[{"date": ...}, ...]`)인 경우에도, 자동으로 `{"version": 1, "items": [...]}` 형태로 감싸서 인식하도록 처리하세요. (단, 백엔드 `test_fenced_json_is_accepted_and_invalid_json_is_rejected` 및 `test_deeply_nested_json_is_reported_as_invalid_input`에서 `[1, 2, 3]`처럼 내부 요소가 dict가 아닌 숫자 배열은 기존처럼 거부해야 합니다!)

### 3. 어떤 형태의 일정 JSON 구조/키 이름이라도 표준 스키마로 변환하는 만능 어댑터 구현
프론트엔드의 `normalizeExternalLlmJsonForRequest(rawText)`와 백엔드의 `parse_external_llm_draft` 전처리 단계에서, LLM이 프롬프트 지시를 어기고 다른 JSON 구조나 키 이름을 사용하더라도 표준 `{"version": 1, "items": [...]}` 구조로 자동 정규화하세요:

1. **다양한 최상위 컨테이너 키 자동 인식**:
   - `items`가 없을 때 `itineraries`, `itinerary`, `schedule`, `schedules`, `events`, `plans`, `plan`, `data`, `activities` 키에 배열이 있으면 이를 `items`로 매핑.
   - 만약 `days`(또는 `daily_schedule`, `itinerary_days`) 배열 안에 날짜별 그룹 객체(`{"date": "2027-01-17", "items" | "activities" | "schedule" | "places": [...]}`)가 중첩된 형태라면, 부모의 `date`를 각 하위 항목에 주입하면서 1차원 `items` 배열로 자동 평탄화(Flatten)하세요.
2. **필드명 별칭(Alias) 자동 매핑**:
   - `date`: `date` || `day_date` || `travel_date` || `start_date` (만약 `"2027.01.17"`이나 `"2027/01/17"` 형식이면 `"2027-01-17"`로 변환, `"Day 1"` / `"1일차"` 형태면 `currentTrip.start_date` 기준으로 날짜 자동 계산)
   - `title`: `title` || `name` || `activity` || `event` || `summary` || `place_name` || `location` (비어 있으면 `"일정"`으로 기본값 부여, 120자 초과 시 자동 슬라이싱)
   - `start_time` / `end_time`:
     - `start_time` || `startTime` || `time` || `start` || `begin_time`
     - `end_time` || `endTime` || `end` || `finish_time`
     - 만약 `start_time` 또는 `time`에 `"09:00 - 10:30"`, `"09:00~11:00"`처럼 범위가 들어있으면 앞 시간을 `start_time`, 뒷 시간을 `end_time`으로 자동 분리.
     - `"오전 9:30"` -> `"09:30"`, `"오후 2:00"` / `"PM 2:00"` -> `"14:00"`, `"9시"` -> `"09:00"`, `"09:00:00"`(초 포함) -> `"09:00"`으로 자동 변환.
     - 만약 `start_time`이 아예 누락되었으면 첫 항목은 `"09:00"`, 이후 같은 날짜 항목은 이전 항목 + 1시간(또는 `"09:00"`)으로 자동 채움.
     - 만약 `end_time`이 `start_time`보다 빠르거나 같으면(예: 자정 넘김 또는 오타), `end_time`을 제거(`null` 처리하여 기본 +1시간 적용)하거나 유효하게 보정.
   - `place_name`: `place_name` || `placeName` || `location_name` || `location` || `place` || `spot` || `address` (최대 200자 슬라이싱)
   - `memo`: `memo` || `description` || `notes` || `note` || `detail` || `details` || `reason` || `tip` (최대 2000자 슬라이싱)
   - `place_url`: `place_url` || `placeUrl` || `map_url` || `mapUrl` || `url` || `link` || `google_maps_url` || `kakao_map_url`
3. **지도 URL(`place_url`) 허용 도메인 확대 (Google + Kakao + Naver)**:
   - `app/services/external_llm_itinerary_service.py`에서:
     - `KAKAO_MAPS_HOSTS = frozenset({"map.kakao.com", "place.map.kakao.com", "kko.to", "m.map.kakao.com"})`
     - `NAVER_MAPS_HOSTS = frozenset({"map.naver.com", "m.map.naver.com", "naver.me"})`
     - `is_allowed_map_url(value: str, provider: str = "any")`가 Google, Kakao, Naver의 유효한 HTTPS 지도 URL을 모두 허용하도록 개선하세요.
     - 프론트엔드 `normalizeExternalLlmJsonForRequest`에서도 Google, Kakao, Naver의 허용된 HTTPS 지도 호스트면 `place_url`을 그대로 살리고, 그 외 잘못된 URL은 빈 문자열(`""`)로 자동 치환하여 일정이 절대 탈락하지 않게 하세요.
   - `app/routers/itineraries.py`의 외부 LLM 일정 Import 시 자동 생성되는 `PlaceCandidate`의 `provider`도 URL 도메인에 따라 `"kakao"`(카카오맵 URL인 경우) 또는 `"google"`로 자동 설정되도록 연결하세요.

---

## Part 2. 국내 여행(`timezone === "Asia/Seoul"`) 시 Kakao 지도 전환 및 국내 친화적 UI 개편

여행 상세 페이지에서 여행의 시간대(`trip.timezone`)가 `"Asia/Seoul"`(국내 여행)로 설정된 경우, 검색과 지도 표시, AI 초안, 외부 링크 등 전반적인 UI와 기능을 카카오맵(Kakao Maps) 및 국내 여행 친화적으로 동작하도록 구현하세요.

### 1. 환경 변수 및 백엔드 설정 추가 (`KAKAO_JAVASCRIPT_KEY`)
현재 서버용 장소 검색 키(`KAKAO_REST_API_KEY`)는 등록되어 있으나, 웹 브라우저에서 카카오 지도를 렌더링하기 위한 **Kakao JavaScript 키** 설정이 없습니다.
1. **`.env.example`**:
   - `KAKAO_REST_API_KEY=` 아래에 다음 주석과 항목을 추가하세요:
     ```env
     # Kakao Maps JavaScript SDK: 국내 여행 브라우저 지도 표시 전용 키 (Kakao Developers > 앱 키 > JavaScript 키)
     KAKAO_JAVASCRIPT_KEY=
     ```
2. **`app/core/config.py`**:
   - `Settings` 클래스에 `kakao_javascript_key: str = ""` 필드를 추가하세요.
3. **`app/routers/pages.py`**:
   - `trip_detail_page` 라우터에서 `kakao_javascript_key = (settings.kakao_javascript_key or "").strip()`를 조회하여 템플릿 컨텍스트(`"kakao_javascript_key": kakao_javascript_key`)로 전달하세요.

### 2. 프론트엔드 통합 지도(`#travel-map`)의 Google Maps / Kakao Maps 듀얼 엔진 구현 (`app/templates/trip_detail.html`)
`tests/test_pages.py`의 기존 Google Maps 스크립트 테스트 계약을 100% 통과시키면서, 국내 여행(`currentTrip?.timezone === "Asia/Seoul"`)일 때 Kakao Maps JavaScript SDK로 지도를 렌더링하세요.

1. **스크립트 로드 및 상태 변수**:
   - 인라인 `<script>` 내부에 `const HAS_KAKAO_JAVASCRIPT_KEY = {{ "true" if kakao_javascript_key else "false" }};` 및 `const KAKAO_JAVASCRIPT_KEY = "{{ kakao_javascript_key | urlencode }}";`를 선언하세요.
   - `tests/test_pages.py`의 `test_trip_detail_places_maps_script_after_inline_script`가 깨지지 않도록 기존 `{% if google_maps_browser_api_key %}<script ... src="https://maps.googleapis.com/maps/api/js?..."></script>{% endif %}` 위치와 형태는 **절대 변경하지 말고 그대로 유지**하세요.
   - 대신 국내 여행(`isDomesticTrip() === true`, 즉 `currentTrip?.timezone === "Asia/Seoul"`)이고 `HAS_KAKAO_JAVASCRIPT_KEY`가 `true`일 때는 JS에서 동적으로 `https://dapi.kakao.com/v2/maps/sdk.js?appkey=${KAKAO_JAVASCRIPT_KEY}&autoload=false` 스크립트를 로드한 뒤 `kakao.maps.load(() => { ... })`를 실행하는 `ensureKakaoMapsSdkLoaded()` 함수를 구현하세요.
2. **지도 엔진 분기 (`getActiveMapProvider()`)**:
   - `isDomesticTrip()`(`currentTrip?.timezone === "Asia/Seoul"`):
     - `HAS_KAKAO_JAVASCRIPT_KEY`가 `true`이면 `"kakao"` 엔진을 사용합니다.
     - 만약 `HAS_KAKAO_JAVASCRIPT_KEY`가 `false`이면:
       - `HAS_GOOGLE_MAPS_BROWSER_API_KEY`가 있으면 Google 지도로 폴백하되, 지도 상태 표시줄(`#travel-map-status`)에 `"국내 여행 지도를 카카오맵으로 보려면 .env에 KAKAO_JAVASCRIPT_KEY를 등록하세요. (현재 Google 지도로 표시 중)"` 안내를 표시합니다.
       - 둘 다 없으면 `"국내 여행 지도를 표시하려면 .env에 KAKAO_JAVASCRIPT_KEY를 설정하세요."`를 표시합니다.
   - 해외 여행(`currentTrip?.timezone !== "Asia/Seoul"`): 기존과 동일하게 `"google"` 엔진을 사용합니다.
3. **Kakao Maps 렌더링 구현 (`refreshTravelMap` 내부 또는 전용 헬퍼)**:
   - `"kakao"` 엔진일 때:
     - `kakaoMap` 인스턴스(`new kakao.maps.Map(mapEl, { center: new kakao.maps.LatLng(37.5665, 126.9780), level: 5 })`), `kakaoInfoWindow`(`new kakao.maps.InfoWindow({ removable: true })`), `kakaoMarkers` 배열을 관리합니다.
     - 여행 시간대가 해외 <-> 국내로 수정(`updateTrip`)될 때 기존 지도 인스턴스를 깔끔히 초기화하고 해당 시간대에 맞는 지도로 다시 그리도록 처리하세요.
     - `points`(일정, 장소 후보, AI 초안) 마커 표시, 클릭 시 인포윈도우 오픈, 일정 카드 포커스(`focusItineraryCard` / `showMobileItineraryDetail`), 다중 마커 `kakao.maps.LatLngBounds` 자동 맞춤(`kakaoMap.setBounds(bounds)`)이 Google 지도일 때와 동일하게 매끄럽게 동작하도록 구현하세요.
     - 모바일에서 지도 탭으로 전환할 때(`setMobileMainTab("map")`) `kakaoMap.relayout()`을 호출하여 타일이 깨지지 않게 처리하세요.

### 3. 국내 여행 시 검색·링크·AI 초안·프롬프트의 국내 지도앱 친화적 UI 전환
`isDomesticTrip()`(`currentTrip?.timezone === "Asia/Seoul"`) 여부에 따라 여행 상세 화면의 UI를 자동으로 최적화하세요:

1. **장소 검색 기본값 및 안내 문구 자동 전환 (`syncDomesticInternationalUI()`)**:
   - `loadTrip()` 및 `updateTrip()` 완료 시 `syncDomesticInternationalUI()`를 호출합니다.
   - 국내 여행(`Asia/Seoul`)이면:
     - 여행 도구 > 장소 검색(`#place-search-form select[name="scope"]`)과 일정 폼 장소 검색(`#item-place-search-scope`)의 선택값을 자동으로 `"domestic"`(`국내 · Kakao`)으로 설정합니다.
     - 검색창 placeholder를 `"예: 성수동 카페, 제주 흑돼지, 해운대 맛집"`으로 변경합니다.
     - 상단 여행 시간대 배지 옆 또는 지도 상단에 `"국내 여행 · Kakao 지도/검색 우선"` 배지 또는 힌트를 자연스럽게 표시합니다.
   - 해외 여행이면:
     - 검색 범위 기본값을 `"international"`(`해외 · Google`)로 설정하고, placeholder를 `"예: 도쿄 스시, 오사카 우메다 카페"`로 설정합니다.
2. **지도/장소 링크 버튼의 국내 지도앱 친화적 표시**:
   - `buildSavedCandidateInfoWindowContent`, `buildAiDraftInfoWindowContent`, 장소 후보 카드 등에서 외부 지도 링크 텍스트를 URL 도메인 또는 제공자에 맞게 동적으로 표시하세요:
     - `place.map.kakao.com` / `map.kakao.com` 또는 `provider === "kakao"` -> `"카카오맵 보기"`
     - `map.naver.com` / `naver.me` -> `"네이버지도 보기"`
     - 그 외 Google Maps -> `"Google 지도 보기"`
   - 국내 여행(`Asia/Seoul`)에서 위도·경도 좌표(`latitude`, `longitude`)가 있는 일정이나 장소 후보의 경우, 카카오맵 길찾기 바로가기 링크(`https://map.kakao.com/link/to/${encodeURIComponent(name)},${latitude},${longitude}`)도 인포윈도우에 `"카카오맵 길찾기 ↗"`로 함께 제공하여 모바일에서 누르면 카카오맵 앱/웹 길찾기로 바로 연결되게 하세요.
3. **국내 여행 시 AI 코스 초안의 Kakao Local 연동 (`app/routers/ai_itinerary.py`, `app/services/ai_itinerary_service.py`, `app/templates/trip_detail.html`)**:
   - 현재 `generate_ai_itinerary_draft`는 무조건 `search_places("international", ...)`(Google Places)만 호출합니다.
   - `generate_ai_itinerary_draft`에 `timezone: str = "Asia/Seoul"`(또는 `trip.timezone`)을 전달하여, `timezone == "Asia/Seoul"`이고 `settings.kakao_rest_api_key`가 설정되어 있으면(단, 기존 `tests/test_ai_itinerary.py` 테스트 호환성을 위해 `kakao_rest_api_key`가 비어 있고 `google_maps_api_key`만 있거나 monkeypatch된 환경에서는 기존 흐름이 깨지지 않도록 안전하게 분기!) Kakao Local 검색(`scope="domestic"`)으로 실제 국내 장소 후보를 수집해 AI 코스를 만들 수 있게 지원하세요.
   - 프론트엔드 `#ai-itinerary-panel`의 제목과 설명도 국내 여행일 때는 `"국내 AI 여행 코스 초안"` / `"여행 스타일과 관심사를 바탕으로 Kakao Local 실제 장소 후보 안에서 날짜별 코스 초안을 구성합니다."`로 자동 변경하세요.
4. **외부 LLM 일정 프롬프트(`buildExternalLlmPrompt`)의 국내/해외 분기**:
   - 국내 여행(`Asia/Seoul`)일 때는 프롬프트의 `place_url` 안내 문구를 다음과 같이 생성하세요:
     `"place_url에는 유효한 HTTPS 카카오맵(예: https://map.kakao.com/link/search/장소명), 네이버지도, 또는 Google 지도 URL을 넣고, 확실하지 않으면 빈 문자열("")로 두세요. 답변에 인용 번호([1], [2] 등)는 절대 포함하지 마세요."`

---

## 최종 검증 및 완료 보고

1. `python -m pytest -q`를 실행해 기존 테스트와 새로 추가/수정한 테스트가 100% 통과하는지 확인하세요.
   - 30개 초과(예: 45개) 일정이 담긴 ChatGPT JSON 응답 분석 및 일괄 추가 테스트
   - 최상위가 배열(`[...]`)이거나 `days` 중첩 구조, 별칭 키(`name`, `time`, `location`, `description`, 카카오맵 `place_url`), 스마트 따옴표/후행 쉼표가 섞인 응답이 정상 정규화되는지 테스트
   - `trip_detail.html`에 `kakao_javascript_key` 전달 시 국내 여행 지도/검색 전환 스크립트가 정상 포함되는지 테스트
2. `git diff --check`로 포맷 오류를 점검하고 수정된 파일 및 테스트 결과를 요약 보고하세요.
