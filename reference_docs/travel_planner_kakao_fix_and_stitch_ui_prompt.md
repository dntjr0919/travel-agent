# Travel Planner 카카오맵 로딩 버그 수정 및 Google Stitch ('Serene Expedition') UI 전면 적용 작업 지시서

아래 프롬프트 전문을 복사하여 코딩 에이전트(Claude Code, Cursor, Windsurf, Copilot 등)에 전달하세요.

---

## 코딩 에이전트 전달용 프롬프트 전문

당신은 이 저장소(FastAPI + SQLAlchemy + Jinja2 + Vanilla JS 기반 `Travel Planner` 웹 앱)를 담당하는 시니어 풀스택 엔지니어이자 프론트엔드 UI 엔지니어입니다.
현재 국내 여행(`timezone === "Asia/Seoul"`)에서 **Kakao Map이 계속 로딩되지 않는 버그를 완벽히 해결**하고, Google Stitch로 디자인한 **'Serene Expedition' 디자인 시스템(데스크톱 & 모바일 UI)**을 기존 기능과 `pytest` 계약(`tests/test_pages.py` 등)을 절대 깨뜨리지 않으면서 적용하세요.

---

## Part 1. 국내 여행(`Asia/Seoul`) 시 Kakao Map 미로딩 원인 해결 및 방어 로직 구현

현재 `.env`에 카카오 JavaScript API 키를 등록했음에도 국내 여행 상세 페이지에서 카카오 지도가 뜨지 않는 문제를 아래 5가지 체크포인트로 수정하세요.

### 1. 환경 변수 이름 호환성 확보 (`app/core/config.py`, `app/routers/pages.py`)
사용자가 `.env`에 키 이름을 `KAKAO_JAVASCRIPT_KEY`, `KAKAO_JAVASCRIPT_API_KEY`, `KAKAO_MAPS_BROWSER_API_KEY`, `KAKAO_MAP_API_KEY` 중 어떤 이름으로 등록했더라도 모두 인식하도록 `Settings`와 `pages.py`를 보강하세요:
- `app/core/config.py`의 `Settings`에 아래 필드들을 선언하세요:
  ```python
  kakao_javascript_key: str = ""
  kakao_javascript_api_key: str = ""
  kakao_maps_browser_api_key: str = ""
  ```
- `Settings`에 프로퍼티 또는 헬퍼 `resolved_kakao_javascript_key`를 만들어 위 3개 값 중 비어 있지 않은 첫 번째 값(`.strip()`)을 반환하게 하고, `app/routers/pages.py`의 `trip_detail_page`에서 이를 `"kakao_javascript_key"`로 템플릿에 전달하세요.

### 2. Kakao Maps SDK 로더 및 `#travel-map` 컨테이너 초기화 순서 버그 수정 (`app/templates/trip_detail.html`)
카카오 지도 SDK(`https://dapi.kakao.com/v2/maps/sdk.js?appkey=...&autoload=false`)는 컨테이너(`#travel-map`)가 `display: none`이거나 높이가 `0`인 상태에서 생성되면 지도가 0x0 크기로 깨져 아무것도 보이지 않으며, `points.length === 0`(좌표 있는 일정이 아직 없을 때)일 때 지도를 생성하기 전에 `return` 해버리면 지도가 아예 뜨지 않습니다. 다음 규칙으로 수정하세요:

1. **SDK 동적 로더(`ensureKakaoMapsSdkLoaded()`) 개선**:
   - `window.kakao && window.kakao.maps && typeof window.kakao.maps.Map === "function"`이면 즉시 `Promise.resolve(true)`를 반환합니다.
   - `window.kakao && window.kakao.maps && typeof window.kakao.maps.load === "function"`이면 `new Promise((resolve) => window.kakao.maps.load(() => resolve(true)))`를 반환합니다.
   - 아직 `<script>`가 없다면 `https://dapi.kakao.com/v2/maps/sdk.js?appkey=${encodeURIComponent(KAKAO_JAVASCRIPT_KEY)}&autoload=false` 스크립트를 동적으로 추가하고, `onload`에서 `window.kakao.maps.load(() => resolve(true))`를 호출합니다.
   - 만약 `onerror`가 발생하면 `kakaoMapLoadFailed = true`로 기록하고, `#travel-map-status`에 **구체적인 원인 안내 메시지**를 표시하세요:
     `"카카오 지도를 불러오지 못했습니다. Kakao Developers 콘솔에서 (1) [앱 키]의 'JavaScript 키'가 맞는지, (2) [플랫폼 > Web]에 현재 주소(${window.location.origin})가 등록되었는지, (3) [제품 설정 > 카카오맵] 사용 설정이 ON인지 확인하세요."`

2. **`#travel-map` 표시 및 인스턴스 생성 순서 보장**:
   - 국내 여행(`currentTrip?.timezone === "Asia/Seoul"`)이고 `HAS_KAKAO_JAVASCRIPT_KEY`가 `true`일 때:
     - `refreshTravelMap()`이 호출되면, 만약 아직 Kakao SDK가 로드되지 않았다면 `"카카오 지도를 불러오는 중입니다..."` 상태를 띄우고 `ensureKakaoMapsSdkLoaded().then(() => refreshTravelMap())`를 호출해 비동기 로드 완료 즉시 지도가 그려지게 하세요.
     - SDK가 준비되었으면 **반드시 `mapEl.style.display = "block"`을 먼저 실행**하고, `mapEl`의 최소 높이(`min-height: 420px`)가 확보된 상태에서 `new kakao.maps.Map(mapEl, { center: new kakao.maps.LatLng(37.5665, 126.9780), level: 7 })`을 생성하세요.
     - 생성 직후 및 탭 전환 시마다 `kakaoMap.relayout()`을 호출하세요.

3. **좌표 있는 일정/후보가 0개(`points.length === 0`)여도 기본 지도는 항상 화면에 표시**:
   - 기존 코드처럼 `if (points.length === 0)`일 때 지도를 숨기거나 인스턴스 생성 전에 `return` 하지 마세요!
   - 먼저 지도 인스턴스(`kakaoMap` 또는 `travelMap`)를 화면에 정상적으로 띄운 뒤(`mapEl.style.display = "block"`), `points.length === 0`이면 기존 마커만 지우고 기본 중심 좌표(예: 여행 목적지에 '제주'가 포함되면 제주도 `33.4996, 126.5312`, '부산'이면 `35.1796, 129.0756`, '경주'면 `35.8562, 129.2247`, '강릉/속초'면 `37.7519, 128.8761`, 그 외 기본 서울 `37.5665, 126.9780`)로 중심을 잡아 **빈 카카오 지도가 정상적으로 화면에 보이도록** 하세요. 그리고 `#travel-map-status`에만 안내 문구(`"선택한 날짜에 표시할 좌표 장소가 없습니다. 일정에 장소를 검색해 연결하면 마커가 표시됩니다."`)를 띄우세요.

4. **`loadTrip()` 완료 시점 연동**:
   - `loadTrip()`에서 `currentTrip`을 받아온 직후 `syncDomesticInternationalUI()`와 `refreshTravelMap()`을 호출하여, 페이지 진입 시 `currentTrip.timezone === "Asia/Seoul"`임이 확인되는 즉시 Kakao Maps 로드가 시작되도록 보장하세요.

---

## Part 2. Google Stitch ('Serene Expedition') 디자인 시스템 전면 반영

Google Stitch에서 추출한 **'Serene Expedition'** 디자인 명세(`DESIGN.md` 및 데스크톱/모바일 시안)를 바탕으로 `app/templates/base.html`과 `app/static/css/app.css`(필요 시 `trip_detail.html`, `trips.html`의 보조 클래스)를 업그레이드하세요.
**중요**: `tests/test_pages.py`가 검사하는 모든 기존 ID, 클래스, 함수 시그니처, 인라인 `<script>` 위치 계약은 100% 그대로 유지해야 합니다.

### 1. 타이포그래피 및 웹폰트 적용 (`app/templates/base.html`, `app/static/css/app.css`)
- `app/templates/base.html`의 `<head>`에 `Plus Jakarta Sans`, `Inter`, `Pretendard` 웹폰트 링크를 추가하세요:
  ```html
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Plus+Jakarta+Sans:wght@600;700;800&display=swap" rel="stylesheet" />
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css" />
  ```
- `:root` 및 기본 폰트 패밀리를 설정하세요:
  - 본문(`body`): `'Inter', 'Pretendard', -apple-system, BlinkMacSystemFont, system-ui, sans-serif`
  - 제목(`h1, h2, h3, .brand`): `'Plus Jakarta Sans', 'Pretendard', -apple-system, BlinkMacSystemFont, system-ui, sans-serif` (`letter-spacing: -0.015em`)

### 2. 컬러 팔레트 및 Elevation(그림자/보더) 토큰 적용 (`app/static/css/app.css`)
`:root` CSS 변수를 Serene Expedition 디자인 토큰으로 정교하게 업데이트하세요:
- **배경 및 서피스(Surface)**:
  - `--color-bg`: `#fbf9f3` (따뜻한 리넨 오프화이트 배경)
  - `--color-surface`: `#ffffff` (순백색 카드 표면)
  - `--color-surface-low`: `#f5f3ed` (보조 입력창/메모 박스/비활성 탭 배경)
  - `--color-surface-container`: `#f0eee8` (세그먼트 컨트롤 트랙, 칩 배경)
  - `--color-border`: `#e7e4dc` (부드럽고 따뜻한 보더 라인)
- **브랜드 & 액센트 컬러**:
  - `--color-primary`: `#006762` (깊고 세련된 딥 틸 그린)
  - `--color-primary-hover`: `#00504c`
  - `--color-primary-container`: `#20827c`
  - `--color-primary-soft`: `#eef7f6` (선택된 탭/타임블록 배경)
  - `--color-primary-fixed`: `#dcf7ee` (민트 배지 배경, 텍스트 `#135b4c`)
  - `--color-secondary-peach`: `#ffece3` (피치 배지 배경 - 식사/카페/여가 강조, 텍스트 `#a8451f`)
- **텍스트 & 그림자**:
  - `--color-text`: `#191c1d`
  - `--color-muted`: `#6e7978`
  - `--shadow-card`: `0 1px 3px 0 rgba(25, 28, 29, 0.03), 0 2px 8px 0 rgba(25, 28, 29, 0.04)`
  - `--shadow-hover`: `0 4px 14px 0 rgba(25, 28, 29, 0.07), 0 1px 3px 0 rgba(25, 28, 29, 0.04)`
  - `--shadow-floating`: `0 12px 32px -4px rgba(25, 28, 29, 0.14), 0 4px 12px -2px rgba(25, 28, 29, 0.06)`

### 3. 화면별 Stitch UI 디테일 스타일링 (`app/static/css/app.css`)

1. **상단 내비게이션 바 (`.topbar`)**:
   - 반투명 글래스모피즘(`background: rgba(251, 249, 243, 0.88); backdrop-filter: blur(12px); border-bottom: 1px solid var(--color-border); position: sticky; top: 0; z-index: 40;`)을 적용하고, `.brand` 로고는 `#006762` 컬러와 `font-weight: 800`로 선명하게 표현하세요.

2. **여행 상세 헤더 (`#trip-header`) & 실시간 접속자 바 (`.presence-bar`)**:
   - `#trip-header`를 둥근 모서리(`border-radius: 20px`), 순백색 배경(`#ffffff`), 부드러운 그림자(`var(--shadow-card)`)가 적용된 히어로 카드로 디자인하세요.
   - 여행 메타 정보(`.trip-header-meta > span`)는 단순 텍스트 대신 **캡슐형 필 배지(`background: #f5f3ed; border: 1px solid #e7e4dc; border-radius: 9999px; padding: 0.3rem 0.75rem; font-size: 0.82rem; font-weight: 500;`)** 형태로 나란히 배치하여 Stitch 데스크톱 시안과 동일한 느낌을 내세요.
   - `.presence-bar`는 헤더 바로 아래(또는 헤더와 자연스럽게 이어지는 바)에 배치하고, 접속자 아바타(`.presence-avatar`)들이 겹쳐진 스택(`margin-left: -6px`, `border: 2px solid #ffffff`) 형태로 보이게 하며, 우측 알림 토글 버튼(`.presence-notification-btn`)은 깔끔한 원형 아이콘 버튼으로 정렬하세요.

3. **데스크톱 2단 스플릿 레이아웃 (`.trip-main-layout`)**:
   - 데스크톱(`min-width: 960px`)에서 좌측 일정 패널(`minmax(0, 1.15fr)`)과 우측 지도 패널(`minmax(380px, 0.85fr)`)이 여유로운 간격(`gap: 1.5rem`)으로 배치되고, 우측 지도 패널(`#trip-map-panel`)은 `position: sticky; top: 5rem;`으로 스크롤 시 따라오도록 다듬으세요.

4. **일정 타임라인 카드 (`.trip-schedule-card .item-card`) & 도보 이동 배지 (`.itinerary-route-leg`)**:
   - 각 `.item-card`는 `border-radius: 16px`, `border: 1px solid #e7e4dc`, `background: #ffffff`, `box-shadow: var(--shadow-card)`를 기본으로 하고, 호버 시 살짝 떠오르는 애니메이션(`transform: translateY(-1px); box-shadow: var(--shadow-hover)`)을 적용하세요.
   - **카테고리별 포인트 컬러 & 필 배지(`.badge`)**:
     - `.category-transportation`: 소프트 민트(`background: #dcf7ee; color: #135b4c;`)
     - `.category-food`: 소프트 피치(`background: #ffece3; color: #a8451f;`)
     - `.category-sightseeing`: 틸 액센트(`background: #e2f4f2; color: #00504c;`)
     - `.category-accommodation`: 인디고/블루 톤(`background: #e8eefc; color: #1e40af;`)
     - `.category-shopping`: 웜 앰버(`background: #fef3c7; color: #92400e;`)
     - 상태 배지(`.status-planned`, `.status-completed`)도 캡슐형(`border-radius: 9999px; font-weight: 600; font-size: 0.75rem`)으로 정돈하세요.
   - **펼쳐진 상세 영역(`.item-details`)**:
     - 배경을 `#f5f3ed`(`--color-surface-low`) 박스로 감싸거나 깔끔한 구분선과 함께 메모 박스를 카드 내부의 부드러운 서브 컨테이너로 표현하고, `.map-link`(`지도 열기 ↗`, `예약 열기 ↗`)는 캡슐형 액션 칩 버튼(`background: #ffffff; border: 1px solid #d1cec4; border-radius: 9999px; padding: 0.35rem 0.8rem; font-weight: 600; color: #006762;`)으로 스타일링하세요.
   - **도보 이동 연결선(`.itinerary-route-leg`)**:
     - Stitch 시안처럼 카드와 카드 사이에 세로 점선 느낌과 함께 둥근 알약 배지(`display: inline-flex; align-items: center; background: #f0eee8; color: #3e4948; border-radius: 9999px; padding: 0.25rem 0.75rem; font-size: 0.78rem; font-weight: 600; margin: 0.25rem 0 0.25rem 1.25rem;`)로 표시하세요.

5. **우측 통합 지도 패널 (`#trip-map-panel`) 및 플로팅 도구 버튼 (`#open-tools-floating-btn`)**:
   - 지도 상단 탭(`.travel-map-tabs`)은 세그먼트 필 형태(`background: #f0eee8; padding: 0.25rem; border-radius: 9999px;`)로 만들고, 활성 탭(`.travel-map-tab.is-active`)은 `#ffffff` 배경과 그림자, `#006762` 굵은 텍스트를 갖도록 디자인하세요.
   - `#travel-map`은 `border-radius: 16px; overflow: hidden; min-height: 440px; border: 1px solid #e7e4dc;`로 깔끔한 프레임 안에 들어오게 하세요.
   - 우측 하단 플로팅 버튼(`#open-tools-floating-btn`)은 Stitch 시안의 다크 틸/차콜 캡슐 버튼(`background: #1b1c18; color: #ffffff; border-radius: 9999px; padding: 0.75rem 1.25rem; box-shadow: var(--shadow-floating); font-weight: 700;`) 스타일로 고급스럽게 표현하세요.

6. **여행 도구 슬라이드 드로어 (`#trip-tools-drawer`)**:
   - 우측에서 부드럽게 열리는 드로어(`background: #ffffff; border-left: 1px solid #e7e4dc; box-shadow: -12px 0 32px rgba(25, 28, 29, 0.12);`) 내부의 탭(`.trip-tools-tab`)에 하단 액티브 인디케이터 바(`#006762`)를 적용하고, 아코디언 아이템(`.tool-accordion-item`)과 장소 후보 카드(`.place-candidate-card`)를 `#f5f3ed` / `#ffffff` 대비가 살아있는 깔끔한 카드로 정돈하세요.

7. **모바일 반응형 (`@media (max-width: 760px)`)**:
   - 모바일 상단 `'일정' | '지도'` 전환 탭(`.trip-mobile-tabs`)을 Stitch 모바일 시안과 동일한 풀와이드 세그먼트 컨트롤(`background: #f0eee8; padding: 0.3rem; border-radius: 14px;`)로 스타일링하고, 선택된 탭이 흰색 카드처럼 올라오게(`background: #ffffff; box-shadow: var(--shadow-card); border-radius: 10px; color: #006762;`) 만드세요.
   - 모바일 일정 카드 내부 패딩과 폰트 크기를 한눈에 들어오도록 최적화하세요.

8. **내 여행 목록 페이지 (`trips.html` 관련 `.trips-page`, `.trip-card`)**:
   - 여행 카드(`.trip-card`)에 넉넉한 라운딩(`border-radius: 20px`), 상단 컬러 액센트 바 또는 세련된 배지 레이아웃, 호버 시 부드러운 엘리베이션 효과를 적용하고, 역할 배지(`.role-owner`, `.role-editor`, `.role-viewer`)를 Stitch 시안처럼 선명한 캡슐형 배지로 스타일링하세요.

---

## 최종 검증 및 완료 보고

1. `python -m pytest -q`를 실행하여 기존 모든 테스트(특히 `tests/test_pages.py`의 마크업/스크립트 계약 테스트 포함)와 신규 테스트가 100% 통과하는지 확인하세요.
2. `git diff --check`로 공백 및 포맷 오류를 점검하세요.
3. 수정된 파일 목록과 카카오맵 로딩 해결 내역, Stitch UI 반영 요약을 보고하세요.
