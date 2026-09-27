# Travel Planner (MVP)

여행 일정을 함께 계획하고 공유하는 협업 웹앱의 MVP입니다. 여행 생성, 날짜/시간별 일정 관리, 초대를 통한 공동 작업, 낙관적 잠금(optimistic locking) 기반 수정 충돌 감지를 지원합니다.

## 이번 단계에서 다루지 않는 것

- 여행지 정보 크롤링(Playwright 등), 가격 비교, 외부 API 연동
- 알림(이메일 발송 포함 — 초대 링크는 화면/응답에 표시만 함), 지도, 예약, 결제
- WebSocket 기반 실시간 동기화 (변경 사항은 새로고침/재조회로 확인)

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
    dependencies.py       # get_current_user 등 FastAPI Depends
    errors.py             # {detail, code} 형태의 공통 예외
  models/                 # SQLAlchemy ORM 모델 (User, Trip, TripMember, Invitation, ItineraryItem)
  schemas/                # Pydantic 요청/응답 스키마
  routers/                # API 라우터 (auth, trips, itineraries, collaborations) + 페이지 라우터(pages)
  services/                # 비즈니스 로직 + 권한 검사 (permission_service 포함)
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

## 비밀번호 재설정

초대 기능과 동일한 패턴(원문 토큰은 URL에만 노출, DB에는 SHA-256 해시만 저장)으로 구현했습니다. 실제 이메일 발송은 하지 않고, 개발용 재설정 링크를 API 응답과 `/forgot-password` 화면에 표시합니다.

- `POST /api/auth/password-reset/request` — 이메일 존재 여부를 노출하지 않기 위해 항상 200을 반환하며, 가입된 이메일일 때만 응답에 `reset_url`을 포함.
- `POST /api/auth/password-reset/confirm` — 토큰과 새 비밀번호로 비밀번호 변경. 만료/재사용된 토큰은 410, 존재하지 않는 토큰은 404.
- 링크 만료 기본 30분 (`PASSWORD_RESET_EXPIRE_MINUTES` 환경변수로 조정).
- 화면: `/forgot-password`(이메일 입력), `/reset-password/{token}`(새 비밀번호 입력). `/login`에 진입 링크 추가.

## 구현 시 선택한 기본값 (요구사항에 명시되지 않은 부분)

- 회원가입 성공 시 자동 로그인 처리 후 프론트엔드에서 `/trips`로 이동 (별도 로그인 단계 생략).
- 초대 만료 기간: 기본 7일 (`INVITATION_EXPIRE_HOURS` 환경변수로 조정 가능).
- 초대 토큰: `secrets.token_urlsafe(32)`로 생성한 원문은 URL에만 노출하고, DB에는 SHA-256 해시만 저장.
- 일정 날짜가 여행 기간을 벗어나는지 검사할 때는 일정의 시각을 여행의 `timezone`으로 변환한 날짜(day)를 기준으로 여행 `start_date` ~ `end_date` 범위와 비교.
- SQLite는 timezone-aware 컬럼을 그대로 지원하지 않으므로, `TZDateTime` 커스텀 타입을 만들어 저장 시 UTC로 정규화하고 조회 시 UTC 오프셋을 다시 부여함(다른 오프셋으로 저장된 값도 일관되게 비교 가능).

## 다음 단계 확장 지점

- **여행지 크롤링 / 가격 비교**: `app/services/` 아래에 `crawling_service.py` 또는 `pricing_service.py`를 신설하고, 별도의 백그라운드 작업(Celery/APScheduler 등)에서 실행 후 결과를 `ItineraryItem`이나 신규 `PlaceSuggestion` 모델에 저장하는 방식으로 확장. Playwright는 이 서비스 계층 내부에서만 사용하고 라우터/모델 계층에는 노출하지 않는 것을 권장.
- **알림**: `services/notification_service.py`를 신설해 초대 생성/수락, 일정 변경 시점에 호출하도록 하고, 실제 발송은 이메일/푸시 프로바이더 어댑터로 분리.
- **실시간 동기화**: 현재는 폴링/새로고침 기반이므로, 추후 FastAPI WebSocket 라우터를 `routers/realtime.py`로 추가하고 `itinerary_service`의 변경 시점에 이벤트를 브로드캐스트하는 방식으로 확장 가능. 기존 optimistic locking(`version` 필드)은 실시간 브로드캐스트와도 호환됨.
