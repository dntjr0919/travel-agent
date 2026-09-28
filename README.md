# Travel Planner (MVP)

여행 일정을 함께 계획하고 공유하는 협업 웹앱의 MVP입니다. 여행 생성, 날짜/시간별 일정 관리, 초대를 통한 공동 작업, 낙관적 잠금(optimistic locking) 기반 수정 충돌 감지를 지원합니다.

## 현재 범위에서 다루지 않는 것

- 여행지 정보 크롤링(Playwright 등), 가격 비교, 외부 API 연동
- 초대 이메일 발송, 일정 변경 알림, 푸시 알림
- 지도, 예약, 결제 기능
- 일정 생성·수정·삭제 결과를 다른 사용자 화면에 즉시 반영하는 실시간 동기화
- Google Docs 수준의 문자 단위 실시간 공동 편집

> 비밀번호 재설정 이메일 발송과 여행 상세 페이지의 공동 작업자 접속 표시(WebSocket)는 구현되어 있습니다.

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

```
app/
  main.py                 # FastAPI 앱 생성, 라우터/정적 파일 등록, 예외 핸들러
  core/
    config.py             # 환경변수 기반 설정 (pydantic-settings)
    database.py           # SQLAlchemy 엔진/세션, WAL+busy_timeout PRAGMA, TZDateTime 타입
    security.py           # 비밀번호 해싱, 세션 쿠키 서명/검증
    presence.py           # 여행별 WebSocket 접속 상태 관리
    dependencies.py       # get_current_user 등 FastAPI Depends
    errors.py             # {detail, code} 형태의 공통 예외
  models/                 # SQLAlchemy ORM 모델 (User, Trip, TripMember, Invitation, ItineraryItem)
  schemas/                # Pydantic 요청/응답 스키마
  routers/                # API 라우터(auth, trips, itineraries, collaborations),WebSocket 라우터(presence), 페이지 라우터(pages)라우터(pages)
  services/                # 비즈니스 로직, 권한 검사(permission_service), SMTP 이메일 발송(email_service)
  templates/              # Jinja2 HTML 템플릿
  static/
    css/app.css
    js/app.js             # 공통 fetch 헬퍼 + 각 화면 스크립트는 템플릿 내 인라인
tests/                    # pytest (in-memory SQLite로 라우터까지 테스트)
alembic/                  # 마이그레이션
.env.example
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

`.env.example` 내용:

```
# SQLite 파일 DB 경로 (SQLAlchemy URL 형식)
DATABASE_URL=sqlite:///./travel_planner.db

# 세션 쿠키 서명에 사용하는 비밀키. 운영 환경에서는 반드시 무작위 긴 문자열로 교체할 것.
SECRET_KEY=change-this-to-a-long-random-secret-key

# 세션 쿠키 만료 시간(초). 기본 7일.
SESSION_MAX_AGE_SECONDS=604800

# 초대 링크 만료 기간(시간). 기본 7일(168시간).
INVITATION_EXPIRE_HOURS=168

# 초대 수락 링크를 만들 때 사용할 프론트엔드 베이스 URL
APP_BASE_URL=http://127.0.0.1:8000
```
# 비밀번호 재설정 링크 만료 기간(분). 기본 30분.
PASSWORD_RESET_EXPIRE_MINUTES=30

# ==================================================
# 이메일(SMTP) 발송 설정
# ==================================================

# 실제 이메일 발송 기능 사용 여부
EMAIL_ENABLED=false

# Gmail 예시: smtp.gmail.com / 587 / TLS
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@example.com

# 실제 앱 비밀번호는 .env 파일에만 입력하고 Git에 올리지 않습니다.
SMTP_PASSWORD=replace-with-app-password

SMTP_FROM_EMAIL=your-email@example.com
SMTP_FROM_NAME=Travel Planner
SMTP_USE_TLS=true

> `.env`에는 SMTP 앱 비밀번호와 `SECRET_KEY` 등 민감 정보가 들어갈 수 있으므로 Git에 커밋하면 안 됩니다. `.env.example`에는 실제 이메일 주소, 앱 비밀번호, 토큰을 입력하지 않습니다.

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

## 수동 테스트 시나리오 (브라우저)

1. `/register`에서 Owner 계정(A) 가입 → 자동 로그인 → `/trips`로 이동.
2. `/trips/new`에서 여행 생성 (예: 2026-11-01 ~ 2026-11-05, Asia/Seoul) → 상세 페이지로 이동.
3. 상세 페이지에서 "일정 추가"로 항목 2~3개 생성 (날짜/시간, 카테고리, 장소, 메모 입력).
4. "구성원 관리" 페이지에서 다른 이메일(B)로 Editor 초대 생성 → 화면에 표시된 개발용 초대 링크 복사.
5. 시크릿 창(또는 다른 브라우저)에서 이메일 B로 회원가입/로그인 후, 복사한 `/invitations/{token}` 링크로 접속 → 초대 수락 → 여행 상세로 이동해 일정이 보이는지 확인.
6. B 계정(Editor)으로 일정 하나를 열어 수정 폼을 띄운 뒤, 저장하지 않은 상태로 A 계정에서 같은 일정을 먼저 수정.
7. B 계정에서 저장 시도 → 409 충돌 배너와 "최신 내용 다시 불러오기" 버튼이 나타나는지 확인.
8. A 계정에서 B의 역할을 Viewer로 변경 → B로 새로고침 시 일정 추가/수정/삭제 버튼이 사라지고 API 직접 호출 시 403이 오는지 확인.
9. A 계정에서 여행 삭제 후 목록에서 사라지는지 확인.

## 필수 오류 코드

`AUTH_REQUIRED`, `INVALID_CREDENTIALS`, `EMAIL_ALREADY_EXISTS`, `TRIP_NOT_FOUND`, `ITINERARY_NOT_FOUND`, `FORBIDDEN`, `INVALID_DATE_RANGE`, `INVALID_TIME_RANGE`, `INVITATION_NOT_FOUND`, `INVITATION_EXPIRED`, `INVITATION_EMAIL_MISMATCH`, `ITINERARY_VERSION_CONFLICT`, `PASSWORD_RESET_TOKEN_INVALID`, `PASSWORD_RESET_TOKEN_EXPIRED` 모두 `{"detail": "...", "code": "..."}` 형태로 반환됩니다.

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

## 다음 단계 확장 지점

- **여행지 크롤링 / 가격 비교**: `app/services/` 아래에 `crawling_service.py` 또는 `pricing_service.py`를 신설하고, 별도의 백그라운드 작업(Celery/APScheduler 등)에서 실행 후 결과를 `ItineraryItem`이나 신규 `PlaceSuggestion` 모델에 저장하는 방식으로 확장. Playwright는 이 서비스 계층 내부에서만 사용하고 라우터/모델 계층에는 노출하지 않는 것을 권장.
- **알림**: `services/notification_service.py`를 신설해 초대 생성/수락, 일정 변경 시점에 호출하도록 하고, 실제 발송은 이메일/푸시 프로바이더 어댑터로 분리.
- **실시간 동기화 확장**: 현재는 `routers/presence.py`와 `core/presence.py`로 여행 상세 페이지의 접속자 상태만 WebSocket으로 실시간 표시합니다. 다음 단계에서는 `itinerary_service`의 생성·수정·삭제 시점에 `itinerary_changed` 이벤트를 같은 여행의 접속자에게 브로드캐스트하고, 다른 브라우저가 일정 목록을 다시 불러오도록 확장할 수 있습니다. 기존 낙관적 잠금(`version` 필드)은 이 구조와 호환됩니다.

## 구현하고자 하는 목표

이 프로젝트는 여러 사용자가 하나의 여행을 함께 계획하고 관리할 수 있는 협업형 여행 일정 웹앱을 목표로 합니다.

### 협업 기능

- 여행 생성자(Owner), 편집자(Editor), 조회자(Viewer) 역할 기반 권한 관리
- 이메일 기반 여행 초대와 초대 수락
- 같은 여행 상세 페이지를 보고 있는 공동 작업자 표시
- 다른 사용자의 일정 생성·수정·삭제 결과를 자동 반영하는 실시간 동기화
- 특정 일정 항목을 누가 수정 중인지 알려 주는 편집 상태 표시
- 일정 수정 충돌을 사용자 친화적으로 해결하는 흐름 개선

### 여행 계획 기능

- 날짜·시간·장소·카테고리·메모 기반 여행 일정 관리
- 여행지 정보 검색, 추천, 가격 비교
- 지도와 장소 정보 연동
- 교통·숙소·관광·식사 등 여행 카테고리별 일정 구성
- 예약 정보와 여행 일정 연결

### 알림과 운영 기능

- 비밀번호 재설정 이메일 발송
- 초대 이메일 발송
- 일정 변경 시 참여자 이메일 또는 푸시 알림
- 운영 환경 HTTPS 설정과 보안 쿠키 적용
- 다중 서버 환경에서 Redis를 통한 WebSocket 접속 상태 공유

## 현재 구현한 목표

### 계정과 보안

- 이메일·비밀번호 기반 회원가입, 로그인, 로그아웃
- `bcrypt` 기반 비밀번호 해시 저장
- `itsdangerous` 서명 기반 HttpOnly 세션 쿠키
- 이메일 존재 여부를 노출하지 않는 비밀번호 재설정 요청
- SHA-256 해시 기반의 재설정 토큰 저장
- 만료 시간 적용 및 재설정 토큰 1회 사용 처리
- SMTP를 통한 실제 비밀번호 재설정 이메일 발송
- `.env`와 `.gitignore`를 이용한 SMTP 비밀번호와 비밀 설정 분리

### 여행과 일정

- 여행 생성, 목록 조회, 상세 조회, 수정, 삭제
- 여행 기간과 일정 시간 범위 검증
- 일정 생성, 조회, 수정, 삭제
- 교통·숙소·관광·식사·쇼핑·기타 카테고리 관리
- 여행 시간대를 고려한 일정 날짜 범위 검증
- 일정 버전 번호를 이용한 낙관적 잠금 기반 수정 충돌 감지

### 공동 작업과 권한

- Owner, Editor, Viewer 역할 기반 권한 관리
- Owner 전용 여행 수정·삭제·구성원 관리
- Owner와 Editor의 일정 생성·수정·삭제 권한
- Viewer의 읽기 전용 접근
- 이메일 주소와 로그인 계정의 일치를 확인하는 초대 수락
- 초대 링크 만료 및 1회 사용 처리
- 같은 여행 상세 페이지에 접속한 공동 작업자 이니셜 아이콘 실시간 표시
- 동일 사용자가 탭을 여러 개 열어도 아이콘이 중복되지 않도록 처리
- 접속자가 탭을 닫거나 페이지를 떠날 때 접속 아이콘 제거

### 개발과 검증

- SQLite WAL 모드, busy timeout, foreign key 활성화
- Alembic 기반 DB 마이그레이션
- FastAPI, SQLAlchemy, Pydantic 기반 계층 분리
- pytest와 in-memory SQLite를 이용한 자동 테스트
- 회원가입, 로그인, 여행, 일정, 초대, 권한, 비밀번호 재설정 흐름 테스트
