# Travel Planner 신규 기능 개발 작업 지시서 (Coding Agent Prompt)

다음 프롬프트 전문을 복사하여 코딩 에이전트(Claude Code, Cursor, Windsurf, Copilot 등)에 전달하세요.

````markdown
당신은 이 저장소(FastAPI + SQLAlchemy + Jinja2 + Vanilla JS 기반 `Travel Planner` 웹 앱)를 담당하는 시니어 풀스택 엔지니어입니다.
이전 리팩터링(Phase 1~6)이 완료된 현재 코드베이스 위에, 기존 기능과 API 호환성, 그리고 `pytest` 테스트 계약(특히 `tests/test_pages.py` 및 `tests/test_external_llm_itineraries.py`)을 절대 깨뜨리지 않으면서 아래 5개 Feature를 순차적으로 구현하세요.

---

## 핵심 제약 조건 (반드시 준수할 것)

1. **기존 테스트 100% 통과 + 신규 기능 테스트 추가**:
   - 각 Feature 구현 후 기존 `pytest` 스위트가 모두 통과하는지 확인하고, 새로 추가된 백엔드 파서/웹소켓 브로드캐스트/신규 API에 대한 단위 테스트를 추가하세요.
   - 특히 `tests/test_pages.py`가 검사하는 DOM ID 및 인라인 `<script>` 마크업 계약(`reservation-image-file`, `initAiItineraryMap`, `PLACE_CANDIDATE_PAGE_SIZE`, `getPlaceCandidatePage`, `reservation-add-accordion-content`, `reservation-transport-accordion-toggle` 등)을 절대 훼손하지 마세요.
2. **DB 스키마 무변경 원칙 (No Alembic Migration)**:
   - 새 테이블이나 컬럼을 추가하지 마세요. 실시간 변경 알림은 기존의 `TripPresenceManager` WebSocket(`/ws/trips/{trip_id}/presence`) 채널을 확장해 전달하고, 1시간 알림 쿨다운 및 미확인(Unread) 빨간 점 상태는 클라이언트 `localStorage`와 기존 모델의 `id`, `created_by`, `updated_by`, `created_at`, `updated_at` 메타데이터를 활용해 관리하세요.
3. **모바일/데스크톱 Progressive Enhancement**:
   - Web Share API(`navigator.share`, `navigator.canShare`) 및 Notification API(`window.Notification`)는 브라우저/OS 지원 여부와 권한 상태를 안전하게 체크하고, 미지원 환경(데스크톱 브라우저 등)에서도 깨짐 없이 클립보드 복사 또는 인앱 토스트 배너로 자연스럽게 동작(Fallback)해야 합니다.

---

## 구현할 기능 명세 (Feature 1 ~ Feature 5)

### Feature 1. 공동 작업자 변경 실시간 감지 및 1시간 쿨다운 푸시(Push) 알림

여행 계획을 공유 중인 **다른 사용자**가 새로운 일정이나 후보(장소 후보, 교통·숙박 예약 후보)를 추가(또는 수정)했을 때 실시간으로 데이터를 갱신하고 알림을 띄웁니다. 단, 알림 피로도를 줄이기 위해 **첫 변경 발생 시 즉시 1회 알림을 보내고, 이후 1시간(3,600,000ms) 동안은 추가 알림을 보내지 않는 쿨다운(Cooldown) 정책**을 적용하세요.

1. **백엔드 WebSocket 이벤트 브로드캐스트 확장 (`app/core/presence.py` & 관련 라우터)**:
   - `TripPresenceManager`에 같은 여행(`trip_id`)을 보고 있는 연결된 소켓들에 변경 이벤트를 전송하는 `async def broadcast_trip_activity(self, trip_id: int, *, actor_id: int, actor_name: str, entity_type: str, action: str, entity_id: int, title: str) -> None` 메서드를 추가하세요.
   - 전송 메시지 포맷:
     ```json
     {
       "type": "trip_activity",
       "trip_id": 1,
       "actor_id": 2,
       "actor_name": "홍길동",
       "entity_type": "itinerary" | "place_candidate" | "booking_candidate",
       "action": "created" | "updated",
       "entity_id": 10,
       "title": "도쿄 타워",
       "timestamp": "2026-11-06T01:30:00Z"
     }
     ```
   - 일정 생성/일괄 생성/수정(`app/routers/itineraries.py`), 장소 후보 생성(`app/routers/places.py`), 예약 후보 생성/수정(`app/routers/travel_booking_candidates.py`) 성공 시 `BackgroundTasks`(또는 비동기 핸들러)를 통해 `presence_manager.broadcast_trip_activity(...)`를 호출하세요.
2. **프론트엔드 실시간 수신 및 1시간 쿨다운 알림 (`app/templates/trip_detail.html`, `app/static/css/app.css`)**:
   - `presenceSocket.onmessage`에서 `data.type === "trip_activity"`를 수신하면:
     - `data.actor_id === currentUser?.id`인 경우(내가 방금 추가/수정한 항목)는 알림을 띄우지 않고 무시합니다.
     - 다른 사용자가 발생시킨 이벤트라면 해당 목록(`loadItineraries()`, `loadPlaceCandidates()`, `loadTravelBookingCandidates()`)을 백그라운드로 즉시 다시 불러오고, 해당 항목을 Feature 2의 '미확인 신규 항목' 목록에 등록합니다.
   - **1시간(3,600,000ms) 알림 쓰로틀링**:
     - `localStorage`의 `trip_${TRIP_ID}_last_push_notified_at` 타임스탬프를 확인합니다.
     - 기록이 없거나 현재 시각과의 차이가 `3600 * 1000`ms(1시간) 이상일 때만 알림을 발송하고, 발송 즉시 현재 시각(`Date.now()`)을 `localStorage`에 저장합니다. (1시간 이내에 다른 사용자의 추가 변경이 계속 발생하더라도 목록 갱신과 빨간 점 표시는 조용히 수행하되, 푸시 알림/배너는 띄우지 않습니다.)
   - **알림 표시 방식 (Browser Notification + 인앱 토스트 배너 병행)**:
     - 상단 또는 적절한 위치에 비침투적인 인앱 토스트 알림을 띄우고, 브라우저 `Notification` 권한이 `"granted"`이면 OS/브라우저 푸시 알림(`new Notification(...)`)도 함께 발생시킵니다. (권한이 `"default"`이면 첫 사용자 상호작용 시 또는 상단 작은 알림 켜기 토글을 통해 권한을 요청할 수 있게 지원하세요.)

---

### Feature 2. 새로 추가된 일정 및 후보에 '미확인 빨간 점(Unread Dot)' 표시

다른 사용자가 새로 추가했거나 내가 아직 확인하지 않은 새로운 일정·장소 후보·예약 후보 항목에 기존 UI 레이아웃을 해치지 않으면서 직관적인 **빨간색 점(Red Dot)** 배지를 표시하고, 사용자가 해당 항목을 확인하면 빨간 점이 사라지도록 구현하세요.

1. **미확인 상태 추적 (`localStorage` 기반)**:
   - 여행별·유형별로 확인 상태를 `localStorage`에 저장합니다 (예: `trip_${TRIP_ID}_seen_entities`에 `{ itineraries: [id...], place_candidates: [id...], booking_candidates: [id...] }` 및 최초 기준 시각 `initialized_at` 보관).
   - **판별 규칙**:
     - 내가 직접 만든 항목(`created_by === currentUser?.id`)은 처음부터 확인된(seen) 것으로 간주해 빨간 점을 표시하지 않습니다.
     - 페이지 최초 진입 시 기존 항목들로 초기 스냅샷을 설정하되, 이후 새로 조회되거나 WebSocket `trip_activity`로 들어온 타인 생성 항목(`!seenSet.has(item.id) && item.created_by !== currentUser?.id`)은 미확인(Unread) 상태로 분류합니다.
2. **빨간 점 UI 배치 및 스타일 (`app/templates/trip_detail.html`, `app/static/css/app.css`)**:
   - `.unread-dot` 클래스를 정의하세요 (크기 `8px × 8px`, 원형 `border-radius: 999px`, 배경색 `#ef4444`, 은은한 외곽 링 `box-shadow: 0 0 0 2px rgba(239, 68, 68, 0.2)`, 레이아웃 밀림 방지 `flex-shrink: 0`).
   - **항목별 표시 위치**:
     - **일정 카드 (`.item-card`)**: `.item-title` 옆 또는 `.item-card-head` 좌측 상단에 깔끔하게 배치.
     - **장소 후보 카드 (`.place-candidate-card`)**: `.place-candidate-title-row h3` 제목 바로 옆에 배치.
     - **예약 후보 카드 (`.travel-booking-candidate-card`)**: `.place-candidate-title-row h4` 제목 바로 옆에 배치.
   - **상위 탭 및 도구 버튼 연동**:
     - 미확인 장소 후보나 예약 후보가 1개 이상 존재할 경우, 헤더/플로팅의 `여행 도구` 버튼(`#open-tools-btn`, `#open-tools-floating-btn`)과 서랍 내부의 해당 탭 버튼(`#trip-tools-tab-places`, `#trip-tools-tab-reservations`), 그리고 예약 아코디언 헤더(`#reservation-transport-accordion-toggle`, `#reservation-accommodation-accordion-toggle`) 우측에도 작은 `.unread-dot`을 표시해 사용자가 새 후보가 어디에 있는지 바로 찾을 수 있게 하세요.
3. **확인(Read) 처리 트리거**:
   - **일정 카드**: 사용자가 해당 일정 카드를 클릭해 상세 내용을 펼치거나(`.item-summary` 클릭) 지도 마커를 클릭해 상세를 볼 때 즉시 해당 일정의 빨간 점을 제거하고 `seen` 목록에 저장합니다.
   - **장소 후보 / 예약 후보 카드**: 사용자가 해당 후보 카드를 클릭/호버하거나 `일정에 추가` / `지도 보기` / `예약 링크` 등 카드 내부와 상호작용할 때(또는 해당 아코디언/목록을 열어 확인했을 때) 빨간 점을 제거하고 상위 탭의 빨간 점 상태도 즉시 재계산(`updateUnreadIndicators()`)하세요.

---

### Feature 3. 외부 LLM 일정 프롬프트 사용자 요청사항 입력칸 및 복사/공유 기능 강화

기존의 `#external-llm-import` 섹션은 여행 제목/목적지/기간만 고정된 프롬프트로 생성하고 단순 복사만 지원합니다. 사용자가 원하는 조건을 직접 덧붙일 수 있게 입력칸을 추가하고, 모바일/데스크톱에서 외부 LLM 앱으로 바로 공유하거나 복사할 수 있게 개선하세요.

1. **사용자 추가 요청사항 입력칸 추가 (`app/templates/trip_detail.html`)**:
   - `#external-llm-import` 섹션 내 `#external-llm-prompt` 위에 사용자가 자유롭게 의도나 조건을 적을 수 있는 입력 필드를 추가하세요:
     ```html
     <label class="external-llm-field">
       추가 요청사항 (선택)
       <textarea
         id="external-llm-custom-request"
         rows="3"
         maxlength="1000"
         placeholder="예: 부모님과 함께 가는 여행이라 도보 이동을 줄이고, 첫째 날 저녁에는 스시 오마카세를 넣어줘."
       ></textarea>
     </label>
     ```
   - `buildExternalLlmPrompt()` 함수를 수정하여, `#external-llm-custom-request`에 입력된 텍스트가 있으면 프롬프트 본문에 `"사용자 추가 요청사항: ..."` 섹션으로 자연스럽게 포함되도록 만들고, `#external-llm-custom-request`에 `input` 이벤트가 발생할 때마다 `#external-llm-prompt` 미리보기 텍스트도 실시간으로 업데이트하세요.
2. **프롬프트 복사 및 앱 공유(Web Share API) 버튼 구성**:
   - 기존 `#external-llm-copy-prompt-btn`(`프롬프트 복사`) 버튼의 ID와 동작은 호환성을 위해 유지하면서, 바로 옆에 `#external-llm-share-prompt-btn`(`외부 앱으로 공유`) 버튼을 나란히 배치하세요.
   - 사용자가 `#external-llm-share-prompt-btn`을 누르면:
     - 먼저 클립보드에도 최신 프롬프트를 자동 복사(일부 LLM 앱이 공유 인텐트 수신 시 클립보드 붙여넣기를 보조로 쓰는 경우 대비)한 뒤,
     - `navigator.share`가 지원되는 환경에서는 `await navigator.share({ title: `${currentTrip.title} 일정 생성 프롬프트`, text: prompt })`를 호출하여 OS 공유 시트(설치된 ChatGPT, Claude, Gemini 앱 등 선택 화면)가 뜨고 선택 시 프롬프트가 해당 앱 입력창으로 바로 전달되게 하세요.
     - 사용자가 공유 시트를 취소(`AbortError`)한 경우 에러 메시지를 띄우지 않고 조용히 처리하며, `navigator.share`를 지원하지 않는 데스크톱 브라우저에서는 클립보드에 복사한 뒤 `"이 브라우저에서는 앱 직접 공유를 지원하지 않아 프롬프트를 클립보드에 복사했습니다. 외부 LLM에 붙여넣어 주세요."`라고 안내하세요.

---

### Feature 4. 예약 스크린샷 외부 LLM 프롬프트 복사/공유 및 JSON 결과 불러오기

유료 Gemini API 키가 없거나 외부 LLM 앱(ChatGPT, Claude, Gemini 앱 등)을 직접 쓰고 싶은 사용자를 위해, **예약 스크린샷 분석 섹션(`#reservation-image-panel`)에서도 외부 LLM으로 프롬프트(+스크린샷 파일)를 복사·공유하고, 외부 LLM이 출력한 예약 JSON을 붙여넣어 바로 예약 폼에 반영**할 수 있게 만드세요.

1. **예약 스크린샷 분석용 외부 LLM 프롬프트 생성 및 복사/공유 UI (`#reservation-image-panel`)**:
   - `#reservation-image-panel` 내부(또는 바로 아래 하위 블록)에 외부 LLM 활용 영역을 추가하세요:
     - 사용자 추가 메모/요청 입력칸 (`#reservation-external-llm-custom-request`, 선택 입력, 예: `"왕복 항공권 중 가는 편만 추출해줘"`)
     - 버튼 2개:
       1. `#reservation-external-llm-copy-btn` (`프롬프트 복사`)
       2. `#reservation-external-llm-share-btn` (`사진 + 프롬프트 공유`)
   - **예약 추출 프롬프트(`buildReservationExternalLlmPrompt()`)**:
     - 백엔드 `ReservationImportAnalyzeOut` 스키마와 완벽히 호환되는 단일 JSON 객체(`kind`: `"transport"` 또는 `"accommodation"`, `transport_mode`: `"flight" | "train" | "intercity_bus" | null`, `title`, `provider_name`, `service_number`, `departure_name`, `arrival_name`, `departure_at`, `arrival_at`, `accommodation_name`, `checkin_at`, `checkout_at`, `price_amount`, `currency`, `booking_url`, `memo`)를 반환하도록 명확한 지시문과 예시 포맷을 생성하세요(사용자 추가 요청사항이 있으면 함께 반영).
   - **복사 버튼 클릭 시 (`#reservation-external-llm-copy-btn`)**:
     - 프롬프트를 클립보드에 복사하고, **반드시 눈에 잘 띄는 안내 문구**로 `"프롬프트를 복사했습니다. 외부 LLM 앱에 붙여넣을 때 예약 스크린샷(사진)도 반드시 함께 첨부해 주세요!"`를 표시하세요.
   - **공유 버튼 클릭 시 (`#reservation-external-llm-share-btn`)**:
     - `#reservation-image-file`에 선택된 이미지 파일(`file`)이 있는지 확인합니다. 파일이 없으면 `"공유할 예약 스크린샷 파일을 먼저 선택해 주세요."` 안내를 띄웁니다.
     - 파일이 있으면 프롬프트를 클립보드에도 백업 복사한 뒤, `navigator.canShare && navigator.canShare({ files: [file], text: prompt })`를 확인하여 **스크린샷 이미지 파일(`files: [file]`)과 프롬프트(`text: prompt`)가 OS 공유 시트를 통해 선택한 외부 LLM 앱으로 한 번에 함께 공유**되도록 `await navigator.share({ title: "예약 스크린샷 분석 요청", text: prompt, files: [file] })`를 실행하세요.
     - 만약 브라우저가 파일+텍스트 동시 공유를 지원하지 않으면 `files: [file]` 공유 후 클립보드 프롬프트 붙여넣기 안내를 띄우거나, 프롬프트 복사로 안전하게 폴백(Fallback)하세요.
2. **외부 LLM 예약 JSON 붙여넣기 및 폼 자동 반영**:
   - 같은 영역에 외부 LLM에서 받은 응답을 붙여넣는 `<textarea id="reservation-external-llm-json">`와 `#reservation-external-llm-apply-btn`(`JSON 결과 반영`) 버튼을 추가하세요.
   - 버튼 클릭 시 Feature 5의 유연한 JSON 추출기로 응답 텍스트에서 JSON 객체를 추출·검증한 뒤, 기존의 `applyReservationAnalysisResult(parsedData, bookingUrl)` 함수를 그대로 호출해 `#external-booking-form`의 모든 필드를 자동으로 채우고 후보 보관함 저장 버튼(`#reservation-analysis-save-candidate-btn`)도 활성화하세요.

---

### Feature 5. 외부 LLM 출력의 유연한 JSON 추출기 (불필요한 설명/마크다운 문구 자동 무시)

외부 LLM이 프롬프트 지시를 어기고 JSON 앞뒤에 인사말, 설명 문구, 마크다운 코드 펜스(`` ```json ... ``` ``), 혹은 부연 텍스트를 섞어서 출력하더라도, **요구한 JSON 형식이 포함된 부분만 정확히 발라내어(Extract) 파싱**하도록 백엔드와 프론트엔드를 모두 개선하세요.

1. **백엔드 일정 JSON 추출기 개선 (`app/services/external_llm_itinerary_service.py`)**:
   - 현재 `parse_external_llm_draft(raw_json: str, trip: Trip)`는 입력 문자열 전체가 순수 JSON이거나 처음부터 끝까지 하나의 코드 펜스로만 감싸져 있어야 동작합니다.
   - 이를 개선하는 헬퍼 함수 `extract_json_object_text(raw_text: str) -> str`를 작성하세요:
     1. 먼저 전체 문자열이 유효한 JSON 객체(`{...}`)인지 시도합니다.
     2. 실패하거나 앞뒤에 잡다한 텍스트가 있다면, 마크다운 코드 블록(`` ```json ... ``` `` 또는 `` ``` ... ``` ``) 내부 블록들을 탐색해 유효한 JSON 객체(최상위 dict, 특히 `"items"` 키를 포함한 dict 우선)가 있는지 확인합니다.
     3. 코드 펜스 없이 일반 텍스트 중간에 JSON 객체가 삽입된 경우(예: `"요청하신 일정입니다:\n{\"version\": 1, \"items\": [...]}\n즐거운 여행 되세요!"`), 문자열 내 `{` 위치부터 `json.JSONDecoder().raw_decode`를 사용해 balanced JSON 객체를 스캔하여 추출합니다(이때 `"items"` 키를 가진 JSON 객체를 최우선 선택).
   - **주의 (기존 테스트 호환성 보장)**:
     - `tests/test_external_llm_itineraries.py`의 기존 테스트 케이스들을 반드시 확인하세요:
       - `test_deeply_nested_json_is_reported_as_invalid_input` (`"[" * 10_000 + "0" + "]" * 10_000`)
       - `test_document_rejects_utf8_payload_over_100_kb`
       - 최상위 구조가 JSON 배열(`[1, 2, 3]`)이거나 잘못된 JSON일 때 반환하는 기존 에러 코드와 한국어 에러 메시지(`AppError`)가 기존 테스트 기대값과 100% 동일하게 유지되어야 합니다.
2. **프론트엔드 예약 JSON 추출기 적용 (`app/templates/trip_detail.html`)**:
   - 프론트엔드에도 동일한 원리의 `extractJsonObjectFromLlmText(rawText)` JS 헬퍼 함수를 구현하여, Feature 4의 예약 스크린샷 외부 LLM 응답(`#reservation-external-llm-json`)에 인사말이나 설명 문구가 섞여 있어도 `"kind"`, `"title"` 등이 포함된 JSON 객체를 자동으로 추출해 `applyReservationAnalysisResult`로 전달하도록 연결하세요.
   - 일정 초안 붙여넣기(`#external-llm-json`) 역시 사용자가 앞뒤 설명 문구가 포함된 채로 붙여넣더라도 백엔드의 `extract_json_object_text`를 통해 매끄럽게 분석 및 가져오기가 동작하도록 하세요.

---

## 최종 검증 및 완료 보고 형식

모든 구현을 마친 후 아래 절차를 실행하여 검증하세요:
1. `python -m pytest -q` (기존 전체 테스트 + 새로 추가한 테스트 모두 통과 확인)
2. `git diff --check` (공백 및 줄바꿈 포맷 오류 확인)

작업 완료 후 다음 항목을 요약해 보고해 주세요:
- Feature 1 ~ 5별 수정/추가된 파일 목록과 핵심 구현 방식
- 추가된 단위/통합 테스트 목록과 `pytest -q` 실행 결과
````
