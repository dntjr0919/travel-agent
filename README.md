# Travel Planner (MVP)

여행 일정을 함께 계획하고 공유하는 협업 웹앱의 MVP입니다. 여행 생성, 날짜/시간별 일정 관리, 초대를 통한 공동 작업, 낙관적 잠금(optimistic locking) 기반 수정 충돌 감지를 지원합니다.

## 현재 구현한 기능

### 계정과 보안

- 이메일·비밀번호 기반 회원가입, 로그인, 로그아웃
- `bcrypt` 비밀번호 해시와 `itsdangerous` 서명 기반 HttpOnly 세션 쿠키
- 실제 SMTP 비밀번호 재설정 이메일 발송
- SHA-256 해시 기반 재설정 토큰 저장, 만료 시간 및 1회 사용 처리
- `.env`와 `.gitignore`를 이용한 API 키·SMTP 비밀번호·비밀 설정 분리

### 여행 일정과 협업

- 여행 생성, 조회, 수정, 삭제 및 여행 기본 정보(제목, 목적지, 시작일, 종료일, 시간대) 수정
- 날짜·시간·장소·카테고리·메모 기반 일정 생성·조회·수정·삭제
- 여행 기간 및 일정 시간 범위 검증
- 일정 버전 기반 낙관적 잠금으로 동시 수정 충돌 감지
- Owner, Editor, Viewer 역할 기반 권한 관리
- 이메일 초대 링크 생성·수락, 이메일 일치 확인, 초대 만료 및 1회 사용 처리
- 여행 상세 페이지 접속자 이니셜 아이콘 실시간 표시(WebSocket)
- 동일 사용자의 여러 탭을 하나의 접속자로 처리
- 일정 메모의 지도 URL을 짧은 외부 지도 링크로 표시
- 작은 화면에서도 일정 카드의 수정·삭제 버튼이 카드 안에 표시되도록 반응형 레이아웃 적용
- Owner가 여행 기본 정보(제목, 목적지, 시작일, 종료일, 시간대)를 수정
- Owner/Editor가 일정 제목, 날짜·시간, 장소, 메모를 수정·삭제
- 일정 메모의 지도 URL을 짧은 외부 지도 링크로 표시
- 작은 화면에서도 일정 카드의 수정·삭제 버튼이 카드 내부에 표시되도록 반응형 레이아웃 적용

### 장소 검색과 후보 보관함

- 해외 장소 검색: Google Places API (New)
- 국내 장소 검색: Kakao Local API
- 여행별 장소 후보 보관함 저장·조회·메모 수정·삭제
- 동일 여행에서 공급자와 외부 장소 ID가 같은 후보의 중복 저장 방지
- Owner/Editor는 후보를 저장·수정·삭제하고, Viewer는 검색·조회만 가능
- 검색 결과와 저장 후보의 외부 지도 링크 제공
- Owner/Editor가 저장한 장소 후보를 일정 생성 폼으로 가져와 일정으로 추가
- 장소 후보의 이름, 카테고리, 주소, 지도 링크, 메모를 일정 입력 폼에 자동 채움
- 일정에 추가한 뒤에도 원본 장소 후보는 보관함에 유지

### 외부 예약 링크 기반 일정 초안 (1차)

- Owner/Editor가 여행 상세 화면에서 외부 예약 링크(URL)를 입력해 일정 초안을 생성
- 브라우저 JavaScript가 URL의 `hostname`만 분석해 예약처(provider)와 유형(kind: 교통/숙소)을 제안
- 사용자가 제목, 가격/통화, 메모와 교통/숙소 핵심 정보를 보완한 뒤 기존 일정 생성 폼으로 자동 채움
- 숙소는 체크인 일정과 체크아웃 일정을 각각 독립적인 일정 초안으로 가져오기 가능
- 기존 일정 저장 버튼을 누르기 전까지 서버 DB에 자동 저장하지 않음

#### 목적

- 외부 예약 정보를 빠르게 일정 초안으로 옮겨 수기 입력 부담을 줄이기 위한 1차 기반 기능

#### 지원 범위

- URL 형식 검증: `http://` 또는 `https://`
- 도메인 힌트 기반 예약처/유형 자동 제안 (사용자 수정 가능)
- 교통: 교통수단, 출발지/도착지, 출발/도착 시각
- 숙소: 숙소명, 체크인/체크아웃 시각
- 교통 초안 및 숙소 체크인/체크아웃 초안을 기존 일정 생성 폼(`#item-form`)에 자동 입력
- 숙소 체크아웃 초안은 독립 일정으로 추가되며 여행 종료일을 자동 변경하지 않음
- 각 초안은 기존 일정 생성 폼에서 사용자가 체크인/체크아웃 시각을 검토한 뒤 저장

### 예약 스크린샷 분석 및 외부 예약 폼 자동 채움 (2단계)

- Owner/Editor가 예약 스크린샷(JPG/PNG 1장, 최대 5MB)을 선택해 Gemini 분석 API를 호출
- Gemini가 추출한 JSON 분석 결과를 기존 “외부 예약 링크로 일정 추가” 폼에 자동 입력
- 교통(출발지/도착지/출발시각/도착시각/교통수단) 및 숙소(숙소명/체크인/체크아웃) 정보 자동 매핑
- 숙소 체크아웃 자동 보정(최소 1박) 및 기존 일정 초안 가져오기 흐름과 완벽 호환
- AI 추출 결과를 DB에 즉시 자동 저장하지 않으며, 사용자가 내용을 검토·보완한 후 기존 일정 생성 폼을 통해 최종 저장
- Viewer 권한 사용자에게는 업로드 UI 및 분석 버튼이 노출되지 않음

#### 사용 흐름

```text
예약 스크린샷 선택 (PNG/JPG, 최대 5MB)
→ [선택] 예약 링크 입력
→ [스크린샷 분석] 클릭
→ Gemini 분석 API 호출 (`POST /api/trips/{trip_id}/reservation-imports/analyze-image`)
→ 기존 "외부 예약 링크로 일정 추가" 폼에 자동 채움
→ 사용자가 날짜, 시간, 장소, 가격 등 검토 및 수정
→ "일정으로 가져오기" 또는 "체크인/체크아웃 일정으로 가져오기" 클릭
→ 기존 일정 폼에서 최종 검토 후 "저장" 버튼으로 DB 저장
```

#### API 설정

- `.env`에 `GEMINI_API_KEY`를 설정해야 동작
- 엔드포인트: `POST /api/trips/{trip_id}/reservation-imports/analyze-image`
- 요청 형식: `multipart/form-data`
  - `file`: `image/jpeg` 또는 `image/png` (최대 5MB)
  - `booking_url`: 선택 문자열
  - `model`: 선택 문자열 (`gemini_flash_lite` 또는 `gemini_flash`)

#### 분석 모델 선택 (MVP)

- 클라이언트는 요청마다 분석 모델을 선택할 수 있습니다.
- 서버는 클라이언트 입력값을 직접 모델명으로 사용하지 않고, 내부 허용 목록으로 실제 Gemini 모델명을 매핑합니다.
- `model`이 없거나 빈 문자열이면 기본값 `gemini_flash_lite`를 사용합니다.
- 허용되지 않은 `model` 값은 `422 RESERVATION_IMPORT_INVALID_MODEL`로 거절합니다.

| 내부 선택값 | UI 이름 | 실제 Gemini 모델명 |
|---|---|---|
| `gemini_flash_lite` | 빠르고 경제적인 분석 | `gemini-3.5-flash-lite` |
| `gemini_flash` | 더 정교한 분석 | `gemini-3.8-flash` |

#### 개인정보 마스킹 안내 및 이미지 비저장 정책

- **민감정보 마스킹 권고**: 예약번호, QR 코드, 바코드, 여권번호, 카드·결제 정보, 전화번호, 이메일, 실명 등 민감한 개인정보는 가린(마스킹) 뒤 업로드하도록 UI에 명시 안내합니다.
- **이미지 비저장 원칙**: 업로드된 원본 이미지 파일은 앱 데이터베이스나 서버 로컬 디스크/정적 파일 디렉터리에 일절 영구 저장하지 않으며, 메모리에서 분석 후 즉시 폐기됩니다.
- **클라이언트 보안**: 브라우저 콘솔, DOM 데이터셋, `localStorage`, `sessionStorage`에 이미지 Base64를 저장하거나 원시 바이트를 로깅하지 않습니다.

#### 분석 응답 보정 및 정규화 규칙 (MVP)

- **시간대(Timezone) 보정**: 스크린샷 이미지에는 대개 시간대 오프셋이 생략되어 있으므로, ISO 형식 날짜/시간에 시간대가 없는 경우 기본 `Asia/Seoul` 시간대(+09:00)로 자동 보정하고 `warnings`에 대조 안내 문구를 추가합니다. 이미 시간대 정보(Z 또는 오프셋)가 있는 값은 보정하지 않고 유지합니다. 자연어 날짜나 비정형 문자열은 임의로 추측하지 않고 실패/null 처리합니다.
- **유형(kind) 및 교통수단(transport_mode) 제한적 정규화**:
  - `kind`: `transportation` -> `transport`, `hotel` / `stay` / `lodging` -> `accommodation`
  - `transport_mode`: `airplane` / `air` -> `flight`, `rail` / `railway` -> `train`, `bus` / `highway_bus` / `express_bus` -> `intercity_bus`
- **마크다운 코드 블록 자동 제거**: 모델이 JSON 응답을 ````json ... ```` 형식으로 감싸서 반환하더라도 안전하게 블록을 제거하고 파싱합니다.
- **안전한 진단 로그**: 디버깅 시 이미지 바이트, API 키, 원본 텍스트, 개인정보를 남기지 않고 유효성 검증 실패 필드 경로 및 에러 유형만 기록합니다.

#### 이번 단계 범위

- 여행 상세 화면의 스크린샷 업로드 및 분석 UI 연동
- Owner/Editor 권한 기반 패널 노출 (Viewer 차단)
- 클라이언트 파일 크기(5MB) 및 포맷(PNG/JPEG) 검증
- 외부 예약 폼 자동 채움 및 경고(warnings) 표시
- 검토 후 기존 일정 생성 흐름을 통한 최종 저장

#### 제외 범위

- 백엔드 API 변경 및 새 엔드포인트 추가
- DB 모델 또는 Alembic 마이그레이션
- OCR(Tesseract), 타 LLM(OpenAI/Claude/Grok) 연동
- 외부 사이트 HTML 무단 크롤링, Playwright/Selenium
- 이미지 장기 보관, 사용자별 API 키 저장, 실제 예약/결제 처리

#### 개인정보 주의사항

- URL 자체를 별도 테이블에 수집·저장하지 않음
- 최종 저장 시점에만 사용자가 확인한 내용이 기존 일정 메모에 반영됨
- 여권번호, 카드번호 등 민감정보는 메모에 입력하지 않도록 운영 정책으로 안내 필요

### 해외 AI 여행 코스 초안 (3단계 MVP)

- Owner/Editor가 여행 스타일, 관심사, 이동 강도, 모델을 입력하면 AI가 날짜별 코스 초안을 제안
- **2단계 흐름 고정**: LLM이 먼저 검색 계획(질의)만 생성하고, 서버가 Google Places 실제 후보를 수집한 뒤, LLM이 후보 ID 안에서만 코스를 구성
- 코스 초안의 각 항목은 실제 Google Places 결과의 `external_place_id`, 이름, 주소, 좌표, 카테고리, 지도 링크를 기반으로 구성
- 초안은 DB에 자동 저장하지 않으며, 사용자가 각 항목의 **후보에 저장** 버튼을 누른 경우에만 기존 후보 보관함 API로 저장
- Viewer는 AI 코스 패널과 생성 결과를 볼 수 없음

#### API

- 엔드포인트: `POST /api/trips/{trip_id}/ai-itinerary-drafts`
- 권한: Owner, Editor
- 요청 본문(JSON)
  - `style`: trim 후 2~300자
  - `interests`: 0~6개 (`culture`, `cafe`, `nature`, `shopping`, `food`, `night_view`)
  - `pace`: `relaxed`, `balanced`, `packed`
  - `model`: `gemini_flash_lite` 또는 `gemini_flash` (없거나 빈 문자열이면 `gemini_flash_lite`)
- 응답(JSON)
  - `destination`, `start_date`, `end_date`, `days`, `warnings`
  - `days[*].items[*]`는 후보 저장에 필요한 장소 필드 + `reason`, `suggested_stay_minutes`

#### 안전장치와 재검증

- 검색 계획 단계: 1~4개 검색어만 허용하고 destination 포함 여부를 검증
- 장소 수집 단계: 검색어별 상위 5개만 사용, 전체 20개 제한, `external_place_id` 기준 중복 제거
- 코스 구성 단계: LLM 응답에서 후보 목록에 없는 ID 제거, 여행 기간 밖 날짜 제거, 하루 4개 제한, 동일 장소 중복 제거(일자 내/일자 간)
- 체류 시간은 30~360분, 30분 단위만 허용
- 유효 항목이 하나도 없으면 `AI_ITINERARY_INVALID_COURSE_RESPONSE` 반환
- LLM 프롬프트/원문 응답/사용자 스타일 전문/Google Places 원문 응답은 로그에 남기지 않음

#### 제외 범위

- Google Maps 지도 임베드
- Google Routes API, 이동 시간·거리 최적화
- 경비 계산/가격 비교
- 일정(ItineraryItem) 자동 저장
- DB 스키마 변경, 작업 큐/Redis, 타 LLM SDK

#### 개인정보와 전송 데이터 주의

- AI 코스 생성 시 입력한 여행 스타일과 Google Places 후보 정보가 선택한 Gemini 모델 제공자 서버로 전송됨
- 민감정보(여권번호, 카드번호, 연락처, 실명 등)는 스타일 입력에 포함하지 않도록 안내 필요
- 결과는 초안이며 영업시간/휴무일/입장 조건을 원본 정보와 반드시 대조해야 함

### 개발과 검증

- SQLite WAL 모드, busy timeout, foreign key 활성화
- SQLAlchemy ORM, Alembic 마이그레이션, Pydantic 검증
- pytest + in-memory SQLite 기반 자동 테스트
- 인증, 여행, 일정, 초대, 권한, 재설정, 장소 후보, 장소 검색, 예약 스크린샷 분석 테스트

## 다음 구현 목표와 범위

### 우선 구현할 기능

- 장소 후보별 우선순위, 좋아요 또는 구성원 투표
- 숙소·항공·철도·버스 후보 보관함과 조건 비교
- 후보별 가격, 통화, 세금 포함 여부, 취소 조건, 조회 시각 기록
- 예약 사이트의 공식 제휴 API 또는 딥링크 기반 예약 페이지 이동
- 일정 생성·수정·삭제 시 같은 여행 참여자 화면을 자동 갱신하는 WebSocket 이벤트

### 이후 검토할 기능

- Google Maps/Kakao Map 지도 임베드와 장소 후보 지도 표시
- 장소 좌표를 이용한 거리 계산과 여행 동선 추천
- 초대 이메일 발송, 일정 변경 이메일·푸시 알림
- 운영 환경 HTTPS, `secure=True` 쿠키, 서버 IP 기반 API 키 제한
- 다중 서버 환경의 Redis 기반 WebSocket 접속 상태 공유
- 여행지 추천, 외부 API 기반 가격 비교

### 현재 의도적으로 제외한 기능

- Playwright 등을 이용한 Trip.com, Agoda 등 예약 사이트의 무단 화면 크롤링
- 앱 안에서 실제 예약·결제 처리
- Google Docs 수준의 문자 단위 실시간 공동 편집
- 별도 대규모 작업 큐, Redis, Docker, Kubernetes 도입

> 예약 가격은 공급자별 세금, 통화, 취소 조건, 회원가, 재고가 함께 달라집니다. 따라서 자동 비교는 공식 제휴 API 또는 제공자가 허용한 데이터 연동 수단을 확보한 뒤 구현합니다.

## 기술 스택

- Backend: Python 3.11+, FastAPI, Uvicorn
- DB: SQLite (WAL 모드 + busy timeout 적용), SQLAlchemy 2.x ORM, Alembic 마이그레이션
- Validation: Pydantic v2
- Frontend: HTML + CSS + Vanilla JS (Jinja2 템플릿, fetch API로 백엔드 호출)
- Test: pytest + httpx (FastAPI TestClient), in-memory SQLite

## 인증 방식 선택: HttpOnly 쿠키 세션 (JWT 대신)

이 프로젝트는 서버 렌더링 Jinja2 페이지와 REST API를 함께 제공하는 구조입니다. 이런 구조에서는 브라우저가 자동으로 쿠키를 첨부해 주는 **HttpOnly 쿠키 세션**이 다음 이유로 더 적합하다고 판단했습니다.

1. 브라우저 JS가 토큰을 직접 다루지 않으므로 XSS로 인한 토큰 탈취 위험이 낮습니다 (HttpOnly).
2. `SameSite=Lax` 설정으로 기본적인 CSRF 방어가 되며, 별도의 토큰 저장/갱신 로직(localStorage 등)이 필요 없습니다.
3. 페이지 이동마다 로그인 상태를 다시 확인해야 하는 서버 렌더링 흐름에 자연스럽게 맞습니다.

구현은 `itsdangerous`로 서명한 `{"user_id": ...}` 페이로드를 쿠키에 저장하는 방식이며, 별도의 세션 테이블 없이 서명 검증과 만료(`max_age`)로 세션을 관리합니다. 비밀번호는 `bcrypt`(passlib)로 해싱해 저장합니다.

## 프로젝트 구조

```text
app/
  main.py                  # FastAPI 앱, 라우터/정적 파일/예외 처리 등록
  core/
    config.py              # .env 기반 설정
    database.py            # SQLAlchemy, SQLite WAL, TZDateTime
    security.py            # 비밀번호 해시, 세션 쿠키 서명·검증
    dependencies.py        # 로그인 사용자 의존성
    presence.py            # 여행별 WebSocket 접속 상태
    errors.py              # 공통 오류 응답
  models/                  # User, Trip, TripMember, Invitation, ItineraryItem, PlaceCandidate
  schemas/                 # API 요청·응답 스키마
  routers/                 # auth, trips, itineraries, collaborations, places, presence, pages
  services/
    permission_service.py  # 역할·접근 권한 검사
    email_service.py       # SMTP 비밀번호 재설정 이메일
    ai_itinerary_service.py
    place_search_service.py
    place_candidate_service.py
    map_providers/         # Google Places, Kakao Local 제공자 어댑터
  templates/               # Jinja2 HTML 화면
  static/                  # 공통 CSS, JavaScript
tests/                     # pytest + in-memory SQLite
alembic/                   # DB 마이그레이션
.env.example               # 공유 가능한 환경변수 예시
requirements.txt
```

## 설치 및 실행

### 1. 가상환경 생성 및 패키지 설치

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. 환경변수 설정

```powershell
Copy-Item .env.example .env
# 필요 시 .env 안의 SECRET_KEY 등을 수정
```

`.env.example`의 핵심 항목:

```env
DATABASE_URL=sqlite:///./travel_planner.db
SECRET_KEY=change-this-to-a-long-random-secret-key
SESSION_MAX_AGE_SECONDS=604800

INVITATION_EXPIRE_HOURS=168
PASSWORD_RESET_EXPIRE_MINUTES=30
APP_BASE_URL=http://127.0.0.1:8000

# SMTP 비밀번호 재설정 이메일
EMAIL_ENABLED=false
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@example.com
SMTP_PASSWORD=replace-with-app-password
SMTP_FROM_EMAIL=your-email@example.com
SMTP_FROM_NAME=Travel Planner
SMTP_USE_TLS=true

# 장소 검색
GOOGLE_MAPS_API_KEY=
KAKAO_REST_API_KEY=

# 예약 스크린샷 분석
GEMINI_API_KEY=
```

> 실제 `.env`에는 SMTP 앱 비밀번호, `SECRET_KEY`, Google·Kakao API 키가 들어갈 수 있습니다. `.env`는 Git에 커밋하지 않으며, `.env.example`에는 실제 키·토큰·이메일 주소를 입력하지 않습니다.

### 3. Alembic 마이그레이션

```powershell
# 최초 1회, 이미 alembic/versions/에 초기 마이그레이션이 포함되어 있으므로 보통은 upgrade만 실행하면 됩니다.
.\.venv\Scripts\alembic.exe upgrade head

# 모델을 변경한 뒤 새 마이그레이션이 필요할 때
.\.venv\Scripts\alembic.exe revision --autogenerate -m "설명"
.\.venv\Scripts\alembic.exe upgrade head
```

### 4. 개발 서버 실행

```powershell
.\.venv\Scripts\uvicorn.exe app.main:app --reload --port 8000
```

브라우저에서 `http://127.0.0.1:8000` 접속 (로그인 여부에 따라 `/trips` 또는 `/login`으로 이동).

### 5. 테스트 실행

```powershell
.\.venv\Scripts\pytest.exe -q
```

테스트는 요청마다 in-memory SQLite + FastAPI `TestClient`를 사용하며, 실제 `.env`/`travel_planner.db`에 영향을 주지 않습니다.

## 수동 테스트 시나리오

1. Owner 계정을 가입하고 여행을 생성한다.
2. Owner가 여행 상세 페이지에서 여행 정보를 수정하고, 제목·목적지·여행 기간·시간대가 변경되는지 확인한다.
3. Owner 또는 Editor가 일정 2~3개를 추가한 뒤, 일정 제목·날짜·시간·장소·메모를 수정하고 일정 삭제가 정상 동작하는지 확인한다.
4. 같은 일정을 두 창에서 수정해 충돌 안내가 표시되는지 확인한다.
5. 다른 계정을 Editor로 초대하고 초대를 수락한다.
6. Owner와 Editor가 같은 여행 상세 페이지를 열어 접속자 이니셜 아이콘이 표시되는지 확인한다.
7. 국내(Kakao)와 해외(Google) 장소를 각각 검색하고 장소 후보로 저장한다.
8. Owner 또는 Editor가 저장된 장소 후보의 "일정에 추가"를 눌러 일정 작성 폼이 자동 입력되는지 확인하고, 날짜·시간 입력 후 새 일정이 생성되는지 확인한다.
9. Owner 또는 Editor가 "외부 예약 링크로 일정 추가"에서 Agoda/Booking.com URL을 입력했을 때 예약처와 숙소 유형이 제안되는지 확인한다.
10. 숙소명·체크인·체크아웃 입력 후 "체크인 일정으로 가져오기"를 눌렀을 때 기존 일정 폼에 숙소 카테고리와 체크인 시각/메모가 채워지는지 확인한다.
11. 같은 숙소 입력에서 "체크아웃 일정으로 가져오기"를 눌렀을 때 기존 일정 폼에 체크아웃 시각 기준 초안이 채워지는지 확인한다.
12. 대한항공/아시아나/코레일/SRT URL과 교통 정보 입력 후 "일정으로 가져오기"를 눌렀을 때 기존 일정 폼에 교통 카테고리와 시간/장소/메모가 채워지는지 확인한다.
13. Viewer 권한 계정에서는 외부 예약 링크 UI가 보이지 않고, 기존처럼 일정 생성/수정 권한이 차단되는지 확인한다.
14. 비밀번호 재설정을 요청하고 실제 이메일 링크로 비밀번호를 변경한 뒤 새 비밀번호로 로그인한다.
15. 일정 카드의 수정·삭제 버튼이 작동하고, 지도 URL이 `지도 열기 ↗` 링크로 표시되는지 확인한다.
16. 브라우저 폭을 줄이거나 확대 비율을 높였을 때 일정 카드의 버튼이 카드 밖으로 밀려나지 않는지 확인한다.
17. Owner 또는 Editor로 로그인 후 "예약 스크린샷으로 분석" 패널이 노출되는지 확인하고, Viewer 계정에서는 패널이 숨겨지는지 확인한다.
18. 스크린샷 파일로 5MB 초과 파일 또는 PDF/GIF 등 미지원 확장자 선택 시 브라우저 오류 메시지가 뜨는지 확인한다.
19. 정상적인 JPG/PNG 예약 스크린샷과 선택 예약 링크를 넣고 [스크린샷 분석] 버튼 클릭 시 "분석 중..." 비활성화 후 결과가 외부 예약 정보 폼에 자동 입력되는지 확인한다.
20. 교통 결과(출발지/도착지/시간/교통수단) 및 숙소 결과(숙소명/체크인/체크아웃 1박 보정)가 정상 채워지고, "일정으로 가져오기" 후 기존 일정 폼에서 최종 저장이 가능한지 확인한다.
21. Owner/Editor로 로그인해 "해외 AI 여행 코스 초안" 패널이 노출되는지, Viewer 계정에서는 패널이 숨겨지는지 확인한다.
22. 스타일/관심사/이동 강도/모델 입력 후 [AI 코스 만들기] 클릭 시 버튼이 비활성화되고 "코스를 만드는 중..."이 표시되는지 확인한다.
23. 날짜별 코스 결과가 표시되고 각 장소 카드의 지도 링크가 새 탭으로 열리는지 확인한다.
24. 카드의 [후보에 저장] 클릭 시 기존 후보 보관함에 저장되고, 자동으로 일정/DB에 즉시 반영되지 않는지 확인한다.

## 필수 오류 코드

모든 API 오류는 `{"detail": "...", "code": "..."}` 형태로 반환됩니다.

- 인증: `AUTH_REQUIRED`, `INVALID_CREDENTIALS`, `EMAIL_ALREADY_EXISTS`
- 여행·권한: `TRIP_NOT_FOUND`, `FORBIDDEN`, `INVALID_DATE_RANGE`
- 일정: `ITINERARY_NOT_FOUND`, `INVALID_TIME_RANGE`, `ITINERARY_VERSION_CONFLICT`
- 초대: `INVITATION_NOT_FOUND`, `INVITATION_EXPIRED`, `INVITATION_EMAIL_MISMATCH`
- 비밀번호 재설정: `PASSWORD_RESET_TOKEN_INVALID`, `PASSWORD_RESET_TOKEN_EXPIRED`
- 장소 후보: `PLACE_CANDIDATE_NOT_FOUND`, `PLACE_CANDIDATE_ALREADY_EXISTS`
- 장소 검색: `PLACE_SEARCH_QUERY_TOO_SHORT`, `INVALID_PLACE_SEARCH_SCOPE`, `PLACE_SEARCH_NOT_CONFIGURED`, `PLACE_SEARCH_TIMEOUT`, `PLACE_SEARCH_PROVIDER_ERROR`
- AI 코스: `AI_ITINERARY_STYLE_TOO_SHORT`, `AI_ITINERARY_STYLE_TOO_LONG`, `AI_ITINERARY_INVALID_INTEREST`, `AI_ITINERARY_INVALID_PACE`, `AI_ITINERARY_INVALID_MODEL`, `AI_ITINERARY_DESTINATION_REQUIRED`, `AI_ITINERARY_INVALID_SEARCH_PLAN`, `AI_ITINERARY_NO_PLACE_CANDIDATES`, `AI_ITINERARY_INVALID_COURSE_RESPONSE`, `AI_ITINERARY_PROVIDER_ERROR`

## 비밀번호 재설정 이메일

비밀번호 재설정은 초대 기능과 같은 보안 원칙을 따릅니다. 원본 토큰은 이메일 링크에만 포함하고, DB에는 SHA-256 해시만 저장합니다.

- `POST /api/auth/password-reset/request`
  - 이메일 존재 여부를 노출하지 않기 위해 항상 동일한 200 응답과 안내 문구를 반환합니다.
  - 가입된 이메일인 경우에만 재설정 토큰을 생성하고 SMTP 이메일 발송 작업을 예약합니다.
  - 재설정 URL은 API 응답이나 `/forgot-password` 화면에 표시하지 않습니다.
- `POST /api/auth/password-reset/confirm`
  - 이메일 링크의 토큰과 새 비밀번호로 비밀번호를 변경합니다.
  - 만료되었거나 이미 사용한 토큰은 `410 PASSWORD_RESET_TOKEN_EXPIRED`를 반환합니다.
  - 존재하지 않는 토큰은 `404 PASSWORD_RESET_TOKEN_INVALID`를 반환합니다.
- 링크 만료 기본값은 30분이며 `PASSWORD_RESET_EXPIRE_MINUTES` 환경변수로 조정할 수 있습니다.
- 화면 경로:
  - `/forgot-password`: 재설정 이메일 요청
  - `/reset-password/{token}`: 새 비밀번호 입력
- 이메일 발송은 FastAPI `BackgroundTasks`를 사용합니다. 따라서 사용자에게 HTTP 응답을 먼저 반환한 뒤 SMTP 전송을 수행합니다.

### SMTP 설정 예시

개발 환경에서는 Gmail SMTP와 앱 비밀번호를 사용할 수 있습니다.

```env
EMAIL_ENABLED=true
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@example.com
SMTP_PASSWORD=your-gmail-app-password
SMTP_FROM_EMAIL=your-email@example.com
SMTP_FROM_NAME=Travel Planner
SMTP_USE_TLS=true
```

> Gmail의 일반 로그인 비밀번호가 아니라 앱 비밀번호를 사용해야 합니다. 실제 `.env` 파일은 Git에 추가하지 않습니다.

## 구현 시 선택한 기본값 (요구사항에 명시되지 않은 부분)

- 회원가입 성공 시 자동 로그인 처리 후 프론트엔드에서 `/trips`로 이동 (별도 로그인 단계 생략).
- 초대 만료 기간: 기본 7일 (`INVITATION_EXPIRE_HOURS` 환경변수로 조정 가능).
- 초대 토큰: `secrets.token_urlsafe(32)`로 생성한 원문은 URL에만 노출하고, DB에는 SHA-256 해시만 저장.
- 일정 날짜가 여행 기간을 벗어나는지 검사할 때는 일정의 시각을 여행의 `timezone`으로 변환한 날짜(day)를 기준으로 여행 `start_date` ~ `end_date` 범위와 비교.
- SQLite는 timezone-aware 컬럼을 그대로 지원하지 않으므로, `TZDateTime` 커스텀 타입을 만들어 저장 시 UTC로 정규화하고 조회 시 UTC 오프셋을 다시 부여함(다른 오프셋으로 저장된 값도 일관되게 비교 가능).
- 여행 기본 정보 수정은 Owner만 가능하며, 여행 기간을 줄일 때 기존 일정이 새 기간을 벗어나는지 자동으로 수정·삭제하지 않는다. 일정 날짜는 별도로 확인·수정해야 한다.
- 장소 후보를 일정으로 추가할 때 후보 ID와 좌표를 일정 테이블에 별도로 연결하지 않고, 장소명은 `location_name`에, 후보 메모·주소·지도 링크는 일정 `memo`에 기록한다.
- 여행 기본 정보 수정은 Owner만 가능하다. 여행 기간을 줄여 기존 일정이 새 기간을 벗어나도 일정이 자동으로 수정·삭제되지는 않으며, 사용자가 일정 날짜를 별도로 확인·수정해야 한다.

