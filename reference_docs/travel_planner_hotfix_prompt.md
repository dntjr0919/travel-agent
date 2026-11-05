# Travel Planner 후속 버그 수정 및 외부 LLM JSON·장소 후보 자동 등록 지시서 (Coding Agent Prompt)

다음 프롬프트 전문을 복사하여 코딩 에이전트(Claude Code, Cursor, Windsurf, Copilot 등)에 전달하세요.

````markdown
당신은 이 저장소(FastAPI + SQLAlchemy + Jinja2 + Vanilla JS 기반 `Travel Planner` 웹 앱)를 담당하는 시니어 풀스택 엔지니어입니다.
이전 작업(Phase 1~6 및 Feature 1~5) 배포 후 확인된 아래 4가지 실사용 문제를 해결하세요. 기존 API 호환성과 `pytest` 테스트 스위트(특히 `tests/test_pages.py` 및 `tests/test_external_llm_itineraries.py`)를 깨뜨리지 않으면서 정확히 수정하고 검증 테스트를 추가하세요.

---

## 해결해야 할 4가지 핵심 과제

### 과제 1. 데스크톱/모바일 상단 헤더의 '여행 도구' 햄버거 버튼(`#open-tools-btn`) 제거 (플로팅 버튼으로 단일화)

현재 모바일에서는 플로팅 버튼(`#open-tools-floating-btn`)만 남았지만, 데스크톱 환경에서는 상단 헤더(`#trip-header`) 우측에 불필요한 햄버거 모양 버튼(`#open-tools-btn`)이 여전히 남아 있습니다.

1. **상단 헤더의 햄버거 버튼 제거 (`app/templates/trip_detail.html`, `app/static/css/app.css`)**:
   - `tests/test_pages.py`에서 `#open-tools-btn` 또는 `.trip-tools-toggle`을 검사하는지 먼저 확인하세요.
   - `renderHeader()` 내부의 `<button id="open-tools-btn" ...>` 마크업과 이벤트 리스너를 제거(또는 `tests/test_pages.py` 호환성이 필요하다면 `hidden` / `display: none !important` 처리)하여 데스크톱에서도 상단 헤더의 햄버거 버튼이 절대 보이지 않도록 하세요.
   - 대신 우측 하단 플로팅 버튼(`#open-tools-floating-btn`)이 **데스크톱과 모바일 모든 화면에서 항상 표시**되도록 `app/static/css/app.css`의 `@media (min-width: 761px)` 숨김 규칙(`#open-tools-floating-btn { display: none; }`)을 제거하세요.
   - Feature 2의 미확인 빨간 점(`.unread-dot`) 표시도 `#open-tools-floating-btn`에 항상 정상 반영되도록 확인하세요.

---

### 과제 2. 알림(Push Notification) 아이콘 전용 토글 버튼으로 개편 (켜기/끄기 상태 유지)

현재 알림 켜기 버튼에 텍스트 문구(`알림 켜기` 등)가 포함되어 있고, 한 번 누르면 버튼이 사라져서 다시 알림을 끄거나 현재 알림 켜짐/꺼짐 상태를 확인할 수 없습니다.

1. **아이콘 전용 토글 버튼 UI (`app/templates/trip_detail.html`, `app/static/css/app.css`)**:
   - 상단 헤더 액션 영역(또는 Presence 바 옆)에 위치한 알림 버튼을 **텍스트 문구 없이 깔끔한 벨(종) 아이콘만 있는 원형/정사각형 아이콘 버튼**으로 변경하세요.
   - 버튼은 알림 권한 승인 후에도 **절대 사라지지 않고 항상 자리에 유지**되어야 합니다.
2. **켜기 / 끄기(On/Off) 양방향 토글 상태 관리**:
   - `localStorage`에 사용자별(또는 여행별) 알림 활성화 상태 키(예: `travel_planner_push_enabled`: `"true"` | `"false"`)를 저장하세요.
   - **상태별 아이콘 및 시각적 표시**:
     - **알림 켜짐 (`enabled === true` & 브라우저 권한 `granted` 또는 인앱 푸시 활성)**: 활성화된 종 아이콘(`🔔` 또는 선명한 벨 SVG), 버튼에 `.is-active` 클래스 부여(테마 컬러 강조), `aria-pressed="true"`, `title="실시간 알림 켜짐 (클릭하여 끄기)"`, `aria-label="실시간 알림 끄기"`.
     - **알림 꺼짐 (`enabled === false` 또는 초기 상태)**: 비활성/음소거 종 아이콘(`🔕` 또는 사선이 그어진 벨 SVG), `.is-active` 해제(회색/보조 톤), `aria-pressed="false"`, `title="실시간 알림 꺼짐 (클릭하여 켜기)"`, `aria-label="실시간 알림 켜기"`.
   - **클릭 시 토글 동작**:
     - 꺼진 상태에서 클릭하면: `enabled = true`로 전환하고, `window.Notification && Notification.permission === "default"`인 경우 `await Notification.requestPermission()`을 요청합니다(설령 브라우저 OS 알림 권한이 거부되거나 미지원이어도 인앱 토스트 푸시 알림은 켜진 상태로 동작). 짧은 토스트/피드백으로 `"실시간 변경 알림을 켰습니다."` 표시.
     - 켜진 상태에서 클릭하면: `enabled = false`로 전환하고 아이콘을 꺼진 상태(`🔕`)로 즉시 바꿉니다. 짧은 토스트/피드백으로 `"실시간 변경 알림을 껐습니다."` 표시.
   - **푸시 발송 연동**:
     - `enabled === false`일 때는 WebSocket `trip_activity` 이벤트가 와도 푸시 알림(OS Notification 및 인앱 토스트 알림)을 띄우지 않습니다(단, 데이터 목록 백그라운드 갱신과 미확인 빨간 점 표시는 그대로 동작).

---

### 과제 3. 외부 LLM(Gemini / ChatGPT / Perplexity) JSON 호환성 및 `place_url` 검증·살리기 개선

실제 외부 LLM 3종(Gemini, ChatGPT, Perplexity)의 출력을 붙여넣었을 때 **Gemini만 전체 일정이 정상 인식되고 ChatGPT와 Perplexity는 실패**하는 문제를 해결하세요. 특히 **ChatGPT처럼 유효한 지도 URL(`place_url`)을 잘 만들어 준 경우에는 이를 버리지 않고 그대로 살려서 활용하고, 형식이 잘못되었거나 허용되지 않는 URL인 경우에만 앱에서 자동으로 빈 문자열(`""`)로 정리**해야 합니다.

#### [원인 진단]
1. **백엔드 `ExternalLlmDraftItem`의 `place_url` 및 기타 실패 처리 방식**:
   - 현재 `app/services/external_llm_itinerary_service.py`는 `place_url`이 허용 규칙에 맞지 않으면 **일정 항목 전체를 `valid: False`(추가 불가)로 탈락**시킵니다.
   - 게다가 ChatGPT가 생성한 `"https://www.google.com/maps/search/?api=1&query=Kansai+International+Airport"` 같은 표준 Google Maps 검색 URL은 매우 유용한 링크임에도, 만약 검증 규칙이나 프론트엔드/백엔드 파서에서 막히면 25개 일정이 통째로 거부됩니다.
   - 또한 ChatGPT/Perplexity 출력은 항목 수가 25~28개(또는 6일 이상 여행 시 30개 초과 가능)이거나, 모바일 Perplexity에서 복사/공유할 때 `[1]`, `[2]` 같은 인용 각주와 출처 블록이 섞여 들어와 JSON 파싱이나 필드 검증이 실패합니다.

#### [구체적 수정 지시]

1. **유효한 `place_url`은 그대로 보존하고, 형식상 오류/비허용 URL만 빈 값(`""`)으로 자동 정리**:
   - `app/services/external_llm_itinerary_service.py`의 `is_allowed_map_url(value, provider="google")`가 ChatGPT 등이 생성하는 표준 Google Maps HTTPS URL(`https://www.google.com/maps/search/?api=1&query=...`, `https://www.google.com/maps/place/...`, `https://www.google.com/maps/...`, `https://maps.google.com/...`)을 정상적으로 허용하는지 확인하세요.
   - **핵심**: 만약 외부 LLM이 출력한 `place_url`이 빈 문자열이 아닌데 형식상 오류이거나 허용되지 않는 도메인/스킴(예: 단축 URL `goo.gl`, 일반 웹사이트, 잘못된 문자열 등)일 때, 일정 전체를 무효(`valid: False`)로 만들지 않고 **자동으로 `place_url = ""`로 비워서 일정을 정상(`valid: True`)으로 살리도록** 처리하세요!
   - **기존 테스트(`tests/test_external_llm_itineraries.py`)와의 호환성 유지 방법**:
     - 먼저 `tests/test_external_llm_itineraries.py`를 열어서 `test_unsafe_or_inactive_map_urls_are_rejected`와 `test_invalid_item_is_reported_without_raising_for_document`가 어떤 함수를 직접 호출하는지 확인하세요.
     - 만약 해당 단위 테스트가 백엔드 `parse_external_llm_draft()`에 잘못된 `place_url`을 넣었을 때 `valid=False`가 반환되는 것을 명시적으로 검사하고 있다면, 백엔드의 `is_allowed_map_url` 및 `ExternalLlmDraftItem.validate_google_maps_url` 자체는 기존 단위 테스트가 통과하도록 그대로 유지하세요.
     - 대신 **프론트엔드(`app/templates/trip_detail.html`의 `analyzeExternalLlmDraft` 및 `importExternalLlmDraft`에서 서버로 요청을 보내기 직전 JSON 정규화 함수 `normalizeExternalLlmJsonForRequest`)** 또는 별도의 전처리 단계에서 각 item의 `place_url`을 검사하여:
       - `https://www.google.com/maps/...` 또는 `https://maps.google.com/...` 형식의 유효한 HTTPS Google Maps URL이면 **그대로 유지**하고,
       - 그 외 잘못된 형식이거나 허용되지 않는 URL이면 **자동으로 `place_url: ""`로 치환**한 뒤 서버에 전송하세요.
       - 이렇게 하면 **기존 백엔드 보안 테스트는 100% 통과**하면서도, **실제 앱에서는 ChatGPT의 유효한 Google Maps URL은 그대로 살아남고, 다른 LLM의 깨진 URL은 빈 값으로 자동 정리되어 일정이 정상 등록**됩니다!
2. **Perplexity 인용 각주(`[1]`, `[2]`) 제거 및 JSON 추출/정규화 강화**:
   - 프론트엔드(`normalizeExternalLlmJsonForRequest`)와 백엔드(`extract_json_object_text`) 양쪽에서:
     - Zero-width 공백(`\u200b`, `\u200c`, `\u200d`, `\ufeff`) 제거.
     - Perplexity 모바일 복사/공유 시 JSON 토큰 주변에 붙는 인용 각주(예: `}[1]`, `",[1][2]`, `][1]` 등)와 텍스트 말미의 `Citations:` / `출처:` 목록을 정규식으로 먼저 제거한 뒤 JSON을 추출하세요.
     - 각 일정 항목의 `title`, `memo`, `place_name` 문자열 끝에 붙은 `[1]`, `[2]` 인용 표시도 깔끔하게 제거하세요.
     - `start_time`, `end_time`이 `"9:00"`처럼 한 자리 시(hour)로 된 경우 `"09:00"`으로 자동 패딩하고, 허용된 7개 키(`date`, `start_time`, `end_time`, `title`, `memo`, `place_name`, `place_url`) 외에 LLM이 임의로 추가한 키는 제거하여 정규화하세요.
     - 프롬프트(`buildExternalLlmPrompt`)에서도 `"place_url에는 유효한 HTTPS Google 지도 URL(예: https://www.google.com/maps/search/?api=1&query=장소명)을 넣고, 확실하지 않으면 빈 문자열(\"\")로 두세요. 답변에 인용 번호([1], [2] 등)는 절대 포함하지 마세요."`라고 안내하세요.

---

### 과제 4. 외부 LLM 일정 가져오기(`import`) 시 유효한 장소(`place_name` + `place_url`)를 '장소 후보 보관함'에도 자동 등록

현재 외부 LLM JSON 일정을 가져올(`POST /api/trips/{trip_id}/external-llm-itinerary/import`) 때는 `ItineraryItem`(일정)만 생성되고 ` memo`에 `지도: https://...` 텍스트로만 들어갈 뿐, **장소 후보 보관함(`PlaceCandidate`)에는 등록되지 않습니다.**
ChatGPT 등이 `place_name`과 유효한 `place_url`을 잘 출력해 주었을 때, 일정을 가져오면서 **장소 후보 보관함에도 자동으로 함께 등록(중복 제외)**되도록 연결하세요.

1. **백엔드 일정 Import 시 장소 후보 자동 생성 (`app/routers/itineraries.py` 또는 `app/services/external_llm_itinerary_service.py`)**:
   -まず `ExternalLlmDraftItemResult` 데이터클래스에 `place_url: str | None = None` 필드를 추가(기본값 `None`으로 두어 기존 테스트 호환성 유지)하고, `parse_external_llm_draft`에서 유효한 `item.place_url`이 있을 때 이를 보존하세요.
   - `POST /api/trips/{trip_id}/external-llm-itinerary/import` 엔드포인트에서 선택된 일정을 생성할 때:
     - 가져온 각 항목에 `location_name`(`place_name`이 비어 있지 않음)과 유효한 `place_url`이 존재하는 경우(또는 `place_name`이 존재하는 경우), 해당 여행(`trip_id`)의 `PlaceCandidate`로도 자동 등록하세요.
     - **중복 방지**:
       - `PlaceCandidate` 테이블에는 `(trip_id, provider, external_place_id)` 유니크 제약조건이 있습니다.
       - 외부 LLM에서 가져온 장소는 `provider="google"`(또는 `"external_llm"` 등 기존 스키마/프론트엔드와 호환되는 값, `PlaceCandidateOut` 및 프론트엔드 제공자 표시 확인), `external_place_id`는 정규화된 `place_url` 또는 `f"llm:{location_name.strip().lower()}"` 해시/식별자를 사용하여, 이미 같은 여행에 동일한 `external_place_id`나 동일한 `name`(+`map_url`)을 가진 후보가 존재하면 건너뛰고(Skip), 없을 때만 새로 추가(`PlaceCandidate` 생성)하세요.
       - 생성된(또는 매칭된) `PlaceCandidate.id`를 일정(`ItineraryItem.place_candidate_id`)에도 연결해 주면 더욱 좋습니다.
2. **프론트엔드 Import 완료 후 장소 후보 목록 자동 새로고침 (`app/templates/trip_detail.html`)**:
   - `importExternalLlmDraft()`에서 `/api/trips/${TRIP_ID}/external-llm-itinerary/import` 호출이 성공하면, 기존 `await loadItineraries();`와 함께 **`await loadPlaceCandidates();`도 호출**하여 새로 자동 등록된 장소 후보들이 장소 후보 보관함과 지도 탭 카운트에 즉시 반영되도록 하세요.

---

## 최종 검증 시나리오 (반드시 테스트로 확인할 것)

1. 질문에 제시된 실제 LLM 출력 샘플 3종:
   - **샘플 1 (Gemini)**: `place_url: ""`인 23개 일정
   - **샘플 2 (ChatGPT)**: `place_url: "https://www.google.com/maps/search/?api=1&query=..."`가 포함된 25개 일정
   - **샘플 3 (Perplexity)**: 28개 일정 + 모바일 복사 시 섞여 들어오는 `[1]`, `[2]` 인용 각주 변형본
   위 3개 샘플을 여행 기간(`2027-01-17` ~ `2027-01-22`)인 `Trip`에 대해 분석(`analyze`) 및 가져오기(`import`)했을 때 **단 하나도 실패하지 않고 전량 `valid: True`로 인식 및 일정 생성**되는지 테스트로 검증하세요.
2. **ChatGPT 샘플 Import 시 장소 후보 자동 등록 검증**:
   - 샘플 2(ChatGPT)를 Import했을 때 `place_name`과 `place_url`이 있는 항목들이 `GET /api/trips/{trip_id}/place-candidates` 목록에 중복 없이 자동 등록(`map_url` 포함)되고, 잘못된 형식의 `place_url`(예: `"not-a-url"`, `"http://unsafe.example.com"`)이 섞인 JSON을 프론트엔드 정규화 후 보냈을 때는 `place_url`이 `""`로 안전하게 비워져 일정 등록이 성공하는지 확인하세요.
3. `python -m pytest -q` 및 `git diff --check`를 실행해 전체 테스트 통과를 확인하고 결과를 보고하세요.
````