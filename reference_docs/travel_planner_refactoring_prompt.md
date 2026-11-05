# Travel Planner 리팩터링 및 최적화 작업 지시서 (Coding Agent Prompt)

다음 프롬프트 전문을 복사하여 코딩 에이전트(Claude Code, Cursor, Windsurf, Copilot 등)에 전달하세요.

```markdown
당신은 이 저장소(FastAPI + SQLAlchemy + Jinja2 + Vanilla JS 기반 `Travel Planner` 웹 앱)를 담당하는 시니어 풀스택 엔지니어입니다.
기존 기능과 API 스키마, 그리고 `pytest` 테스트 계약(특히 `tests/test_pages.py`의 DOM/스크립트 마크업 검증)을 절대 깨뜨리지 않으면서 아래 6개 Phase의 UI/버튼 정리, 프론트엔드 중복 제거, 백엔드 N+1 쿼리 및 공통 유틸리티 리팩터링을 순차적으로 수행하세요.

---

## 핵심 제약 조건 (반드시 준수할 것)

1. **기존 테스트 100% 통과 유지**:
   - 각 Phase를 마칠 때마다 `python -m pytest -q`를 실행해 전체 테스트가 통과하는지 확인하세요.
   - 특히 `tests/test_pages.py`는 다음 계약을 엄격하게 검사합니다:
     - `trip_detail.html` 안에 인라인 `<script>`가 존재해야 하며, `const reservationImageFileInput = document.getElementById("reservation-image-file");` 및 `window.initAiItineraryMap = function initAiItineraryMap()`이 인라인 `<script>` 내부에 위치해야 합니다.
     - `const PLACE_CANDIDATE_PAGE_SIZE = `와 `function getPlaceCandidatePage(` 함수 시그니처 및 위치(`function renderPlaceCandidates(` 직전)가 유지되어야 합니다.
     - `id="reservation-add-accordion-content"`와 `id="reservation-transport-accordion-toggle"` 등의 핵심 ID가 유지되어야 합니다.
2. **API 입출력 호환성 유지**:
   - 모든 엔드포인트의 URL, HTTP 메서드, 요청/응답 JSON 필드명(`created_by_name`, `updated_by_name` 등)과 상태 코드를 변경하지 마세요.
3. **DB 마이그레이션 불필요**:
   - 테이블 컬럼이나 스키마 구조는 변경하지 마세요(Alembic 새 리비전 생성 금지).

---

## 작업 절차 (Phase 1 ~ Phase 6)

### Phase 1. `trip_detail.html` 불필요한 버튼 정리 및 접근성 버그 수정

1. **`openToolsDrawer()` 바깥으로 빠져나온 코드 버그 수정**:
   - `app/templates/trip_detail.html`에서 `function openToolsDrawer()` 블록 바로 아래(함수 바깥)에 잘못 위치해 페이지 로드 즉시 실행되는 아래 코드를 찾아 `openToolsDrawer()` 함수 내부 마지막 줄로 이동하세요:
     ```javascript
     document.getElementById("open-tools-floating-btn")?.setAttribute("aria-expanded", "true");
     ```
2. **여행 도구 열기 버튼 중복 해소**:
   - 상단 헤더의 `#open-tools-btn`과 우측 하단 플로팅 버튼 `#open-tools-floating-btn`이 동시에 노출되어 중복됩니다.
   - DOM에서 두 버튼은 모두 유지하되(이벤트 리스너 및 호환성 보존), `app/static/css/app.css`에서 데스크톱(`min-width: 761px`)에서는 `#open-tools-floating-btn`을 숨기고(`display: none`), 모바일(`max-width: 760px`)에서는 헤더의 `#open-tools-btn`을 숨기고 `#open-tools-floating-btn`만 노출하도록 반응형 역할을 분리하세요.
3. **'예약 후보 추가' 아코디언 내 불필요한 2중 버튼 제거**:
   - 사용자가 `#reservation-add-accordion-toggle`(`예약 후보 추가`)을 열었을 때 내부의 `#travel-booking-candidate-add-btn`(`후보 추가`)을 또 누르지 않아도 바로 입력 폼(`#travel-booking-candidate-form`)을 사용할 수 있도록 개선하세요.
   - `setToolAccordion(groupName, itemName)`에서 `groupName === "reservations"`이고 `nextItem === "add"`로 열릴 때, 폼이 닫혀 있다면 자동으로 `openTravelBookingCandidateForm()`을 호출해 폼을 즉시 표시하세요.
   - `#travel-booking-candidate-add-btn`은 불필요하게 따로 노출되지 않도록 숨김 상태를 유지하거나, 수정 모드에서 새 후보 작성으로 초기화할 때만 보조적으로 동작하게 정리하세요.
   - `#travel-booking-candidate-cancel-btn`(`취소`) 클릭 시 폼을 초기화하고 아코디언(`setToolAccordion("reservations", null)`)도 함께 닫히도록 연결하세요.
4. **아코디언 하단 중복 닫기 버튼(`.tool-accordion-back`) 제거**:
   - `tests/test_pages.py`에서 `.tool-accordion-back` 또는 `data-tool-accordion-close`를 검사하는지 먼저 확인하세요.
   - 테스트에서 검사하지 않는다면, 아코디언 본문 하단에 반복되는 5개의 `<button type="button" class="tool-accordion-back secondary" data-tool-accordion-close="...">... 목록으로</button>` 버튼과 관련 JS 이벤트 리스너, CSS(`.tool-accordion-back`)를 제거하여 세로 스크롤 낭비를 줄이세요.

---

### Phase 2. `trip_detail.html` 프론트엔드 중복 JS 로직 통합

`tests/test_pages.py`의 문자열 인덱스 검증(`PLACE_CANDIDATE_PAGE_SIZE`, `getPlaceCandidatePage`, `renderPlaceCandidates`, `reservationImageFileInput`, `initAiItineraryMap`)을 건드리지 않으면서 아래 중복 코드를 정리하세요:

1. **불필요한 1줄 래퍼(Wrapper) 함수 제거**:
   - `closeTripEditForm()` -> `hideTripEditForm()`으로 통일
   - `closeQuickTimeEditForm()` -> `hideQuickTimeEditPanel()`으로 통일
   - `refreshSavedCandidatesMap()` -> `refreshTravelMap()`으로 통일
   - `setExternalBookingPanelVisibility(canEdit)` -> `setToolsDrawerPermissions(canEdit)` 직접 호출로 정리
2. **날짜/시간 오프셋 헬퍼 함수 통합**:
   - `addOneHourToDatetimeLocal(value)`와 `addOneDayToDatetimeLocal(value)`의 중복된 날짜 파싱 및 `YYYY-MM-DDTHH:mm` 포맷팅 로직을 공통 헬퍼 `shiftDatetimeLocal(value, { hours = 0, days = 0 })`로 통합하세요(기존 함수명이 호출되는 곳은 공통 헬퍼를 쓰도록 교체).
3. **장소 선택 -> 일정 폼 반영 로직 통합**:
   - `applyItemPlaceSelection(place)`와 `openItineraryFormFromPlace(place)`에서 중복 수행하는 좌표 유효성 검사(`Number.isFinite`), hidden input 세팅(`place_provider`, `external_place_id`, `latitude`, `longitude`), 카테고리 자동 매핑(`getItineraryCategoryForPlace`), 상태 메시지 표시(`setItemPlaceSearchStatus`) 로직을 하나의 공통 함수로 통합하세요.
4. **장소 검색 API 호출 공통화**:
   - `searchItemPlaces(scope, query)`와 `searchPlaces(scope, query)`에서 중복되는 `/api/trips/${TRIP_ID}/places/search` 호출 및 에러 파싱 로직을 공통 fetch 헬퍼 함수로 추출하세요.
5. **타임존 `<option>` 목록 중복 제거**:
   - `app/templates/trip_form.html`과 `app/templates/trip_detail.html`에 중복 하드코딩된 15개 시간대 `<option>` 목록을 Jinja2 매크로 또는 부분 템플릿(예: `app/templates/_timezone_options.html`의 `{% include %}`)으로 추출하여 한 곳에서 관리하세요. (`trip_form.html`의 기본 `Asia/Seoul` `selected` 속성과 `trip_detail.html`의 `disabled` 안내 옵션 차이만 반영할 것.)

---

### Phase 3. 예약 입력 폼 UX 및 중복 코드 개선

`#external-booking-form`(외부 예약 링크로 일정 추가)과 `#travel-booking-candidate-form`(예약 후보 추가)의 중복 코드와 UX 혼선을 줄이세요 (`tests/test_pages.py` 통과 보장):

1. **예약 메모 생성 로직 통합**:
   - `buildExternalBookingMemo()`와 `buildAccommodationDraftMemo()`, 그리고 `openItemFormFromBookingCandidate()` 내부의 메모 조립 로직에서 공통으로 쓰이는 예약 링크/예약처/가격/체크인·아웃 포맷팅을 공통 헬퍼 함수로 추출하세요.
2. **날짜/시간 범위 및 URL 검증 공통화**:
   - `parseExternalBookingUrl()`과 `safeTravelBookingUrl()`로 나뉜 URL 프로토콜(`http:`, `https:`) 검증 로직을 재사용하도록 정리하고, 출발/도착 및 체크인/체크아웃 시간 선후 관계 검증을 공통 함수로 묶으세요.

---

### Phase 4. `app/static/css/app.css` 중복 스타일시트 정리

1. **연속 중복 선언된 셀렉터 제거**:
   - `.trip-empty-state > strong`, `.trip-empty-state strong`, `.travel-booking-timepoint span`, `.external-llm-selection-controls` 등 동일하게 두 번 연속 선언된 셀렉터를 하나로 합치세요.
2. **상·하단 분산 재정의 규칙 병합**:
   - 파일 상단과 하단에 나뉘어 중복 정의된 `.trip-tools-tab`, `.travel-map-controls`, `#conflict-banner`, `.member-table` 등의 속성들을 최종 렌더링 결과가 변하지 않도록 하나의 규칙 블록으로 깔끔하게 병합하세요.

---

### Phase 5. 백엔드 N+1 DB 쿼리 최적화 (SQLAlchemy `joinedload`)

목록 조회 시 각 행마다 `db.get(User, ...)`을 반복 실행하는 N+1 쿼리 문제를 해결하세요.

1. **`app/services/itinerary_service.py`**:
   - `ItineraryItem` 조회 시 `sqlalchemy.orm.joinedload`를 사용해 `ItineraryItem.creator`와 `ItineraryItem.updater`를 함께 로드하도록 수정하세요.
   - `_serialize(db: Session, item: ItineraryItem)`에서 `item.__dict__.get("creator")`가 이미 로드되어 있으면 추가 `db.get(User, ...)` 쿼리 없이 `item.creator` / `item.updater` 관계를 바로 읽고, 없을 때만 fallback으로 `db.get`을 호출하도록 최적화하세요.
2. **`app/services/place_candidate_service.py`**:
   - `PlaceCandidate` 목록 조회(`stmt`)에 `joinedload(PlaceCandidate.creator)`를 추가하고, `_serialize`에서 `candidate.creator`를 우선 사용하도록 수정하세요.
3. **`app/services/travel_booking_candidate_service.py`**:
   - `list_travel_booking_candidates`의 `stmt`에 `joinedload(TravelBookingCandidate.creator)`를 추가하고, `_serialize`에서 `candidate.creator`를 우선 사용하도록 수정하세요.

---

### Phase 6. 백엔드 중복 유틸리티 함수 통합

여러 파일에 복사-붙여넣기 되어 있는 백엔드 유틸 함수를 공통 모듈로 추출하세요(기존 테스트에서 직접 import하는 함수가 있다면 호환성을 위해 re-export 유지):

1. **`utcnow()` 통합**:
   - `app/core/database.py`에 `def utcnow() -> datetime:` (`datetime.now(timezone.utc)`)을 정의하고, `app/models/` 산하 7개 모델 파일(`user.py`, `trip.py`, `itinerary.py`, `invitation.py`, `password_reset.py`, `place_candidate.py`, `travel_booking_candidate.py`)에서 중복 정의된 `def _utcnow()`를 제거한 뒤 `utcnow`를 import해 사용하세요.
2. **`hash_token(token: str)` 통합**:
   - `app/core/security.py`에 `def hash_token(token: str) -> str:`을 정의하고, `app/services/auth_service.py`와 `app/services/invitation_service.py`에서 이를 재사용하세요.
3. **LLM 응답 정리 및 모델 해석 함수 통합**:
   - `app/services/ai_itinerary_service.py`와 `app/services/reservation_import_service.py`에 중복 구현된 `_strip_markdown_code_fence(text: str)`와 Gemini 모델 키 검증 로직(`resolve_ai_itinerary_model` / `resolve_reservation_analysis_model`)을 `app/services/llm/`(예: `gemini_provider.py` 또는 `utils.py`)에 공통 함수로 정의하고 양쪽 서비스에서 호출하세요.
4. **`app/routers/pages.py` 세션 사용자 조회 정리**:
   - `pages.py`에서 `SessionLocal()`을 수동으로 여는 `_current_user_for_page(request)` 대신, `app/core/dependencies.py`의 `get_current_user_optional`을 FastAPI `Depends(get_current_user_optional)`로 주입받도록 정리하세요. (`tests/conftest.py` 및 `tests/test_pages.py` 통과 여부를 반드시 확인하세요.)

---

## 최종 검증 및 완료 보고 형식

모든 수정을 마친 후 아래 명령을 실행하여 이상이 없는지 검증하세요:
1. `python -m pytest -q` (전체 테스트 통과 확인)
2. `git diff --check` (공백/포맷 오류 확인)

작업 완료 후 다음 항목을 요약해 보고해 주세요:
- Phase별 수정된 파일 목록 및 핵심 변경 내역
- 제거된 중복 코드 줄 수 및 불필요한 UI 요소 요약
- `pytest -q` 실행 결과
```
