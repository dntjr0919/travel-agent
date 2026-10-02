# Travel Planner

여행 일정과 장소 후보를 구성원과 함께 관리하는 협업형 여행 계획 웹 애플리케이션입니다.

사용자는 여행을 만들고 구성원을 초대해 역할별로 협업할 수 있습니다. 일정, 장소 후보, 지도, AI 코스 초안, 예약 정보를 하나의 여행 화면에서 관리하는 것을 목표로 합니다.

> 개발 환경 기준: Windows + VS Code + PowerShell + SQLite

---

## 주요 기능

### 계정 및 인증

- 회원가입, 로그인, 로그아웃
- 세션 쿠키 기반 로그인 유지
- 비밀번호 재설정 요청 및 재설정
- 개발 환경에서 SMTP 설정을 통한 비밀번호 재설정 이메일 발송 지원

### 여행 및 협업

- 여행 생성, 조회, 수정, 삭제
- 여행 제목, 목적지, 기간, 시간대 관리
- 초대 링크 기반 구성원 초대
- 구성원 역할 관리
  - `owner`: 여행 정보·구성원·일정·장소 후보를 관리
  - `editor`: 일정 및 장소 후보를 추가·수정·삭제
  - `viewer`: 여행, 일정, 장소 후보, 지도를 조회
- 여행 상세 화면에서 현재 접속 중인 구성원 표시

### 일정 관리

- 일정 생성, 조회, 수정, 삭제
- 일정 카테고리
  - 교통
  - 숙소
  - 관광
  - 음식
  - 쇼핑
  - 기타
- 일정 상태
  - 예정 (`planned`)
  - 완료 (`completed`)
  - 취소 (`cancelled`)
- 일정 시간순 정렬
- 일정 상세 펼침/접기
- Owner와 Editor의 수정·삭제 메뉴 제공
- 낙관적 잠금 기반 수정 충돌 처리  
  - 낙관적 잠금: 여러 사용자가 같은 일정을 동시에 수정할 때, 먼저 저장된 수정 내용을 보호하는 방식입니다.

### 장소 검색 및 장소 후보

- 해외 장소 검색: Google Places API
- 국내 장소 검색: Kakao Local API
- 여행별 장소 후보 보관함
- 장소 후보 저장, 메모 수정, 삭제
- 장소 후보에서 일정 추가
- 장소 정보에 이름, 주소, 카테고리, 지도 URL, 좌표 저장
- Google/Kakao 장소 검색 결과를 일정 폼에서 바로 선택 가능

### 일정 위치와 통합 지도

- 일정에 아래 위치 메타데이터 저장
  - 장소 후보 ID
  - 장소 제공자 (`google` / `kakao`)
  - 외부 장소 ID
  - 위도
  - 경도
- Google Maps JavaScript API 기반 통합 지도
- 지도 탭
  - 일정
  - 장소 후보
  - AI 코스 초안
- 일정 탭에서 날짜별 일정 장소 마커 표시
- 장소 후보 탭에서 저장 후보 마커 및 카테고리 필터 제공
- AI 코스 초안 탭에서 날짜별 추천 장소 마커 표시
- 일정 폼에서 장소 검색 후 선택하면 메모에 지도 링크 자동 추가
- 지도 마커 팝업에서 일정 제목을 클릭하면 연결된 외부 지도 열기

> 기존에 좌표 없이 만든 일정은 지도에 표시되지 않을 수 있습니다. 새 일정은 장소 검색 결과를 선택한 뒤 저장하면 좌표가 함께 저장됩니다.

### AI 여행 코스 초안

- Gemini API 기반 AI 여행 코스 초안 생성
- 사용자 입력
  - 여행 스타일
  - 관심사
  - 이동 강도
  - Gemini 모델 선택
- AI가 검색 계획을 만들고, Google Places API로 실제 장소 후보를 수집
- AI가 실제 장소 후보 범위 안에서 날짜별 코스를 제안
- 서버가 날짜 범위, 중복 장소, 체류 시간 등을 검증
- AI 초안 장소를 후보 보관함에 저장 가능
- Google Routes API 기반 도보 이동 거리·시간 계산

> AI 코스 초안은 현재 브라우저 메모리에 임시로 보관됩니다. 초안 자체를 DB에 저장하는 기능은 아직 구현하지 않았습니다.

### 예약 및 교통·숙소 정보

- 예약 스크린샷 분석
  - PNG/JPG 이미지 업로드
  - Gemini API로 교통 또는 숙소 정보 추출
  - 분석 결과를 외부 예약 링크 입력 폼에 반영
- 외부 예약 링크 기반 일정 초안
  - 항공, 기차, 버스 등 교통 일정
  - 숙소 체크인·체크아웃 일정
- 알려진 예약 서비스·교통 도메인의 제공자 및 종류 힌트 지원
- 일정 메모에서 아래 형식의 링크를 클릭 가능한 버튼으로 표시
  - `지도: https://...` → 지도 보기
  - `예약: https://...` → 예약 보기

> 예약 링크에는 로그인 세션, 예약번호, 탑승객 정보, 결제 정보가 포함될 수 있습니다. 구성원에게 공유해도 안전한 링크만 저장하세요.

---

## 권한 정책

| 기능 | Owner | Editor | Viewer |
|---|:---:|:---:|:---:|
| 여행 조회 | 가능 | 가능 | 가능 |
| 일정 조회 | 가능 | 가능 | 가능 |
| 장소 후보 조회 | 가능 | 가능 | 가능 |
| 통합 지도 조회 | 가능 | 가능 | 가능 |
| 일정 생성·수정·삭제 | 가능 | 가능 | 불가 |
| 장소 후보 저장·수정·삭제 | 가능 | 가능 | 불가 |
| AI 코스 초안 생성 | 가능 | 가능 | 불가 |
| 예약 정보 입력 | 가능 | 가능 | 불가 |
| 여행 정보 수정 | 가능 | 불가 | 불가 |
| 구성원 초대·역할 변경·제거 | 가능 | 불가 | 불가 |

---

## 기술 스택

| 구분 | 사용 기술 |
|---|---|
| Backend | Python, FastAPI |
| ORM | SQLAlchemy |
| 데이터 검증 | Pydantic |
| DB migration | Alembic |
| 데이터베이스 | SQLite |
| 화면 템플릿 | Jinja2 |
| Frontend | 순수 HTML, CSS, JavaScript |
| 지도 | Google Maps JavaScript API |
| 장소 검색 | Google Places API, Kakao Local API |
| 경로 계산 | Google Routes API |
| AI | Gemini API |
| 테스트 | pytest, httpx |

---

## 프로젝트 구조

```text
travel-agent/
├─ app/
│  ├─ core/                 # 설정, DB, 보안, 예외 처리, Presence
│  ├─ models/               # SQLAlchemy 모델
│  ├─ routers/              # FastAPI API 및 페이지 라우터
│  ├─ schemas/              # Pydantic 요청/응답 모델
│  ├─ services/             # 비즈니스 로직 및 외부 API 연동
│  │  ├─ llm/               # Gemini 연동
│  │  └─ map_providers/     # Google Places, Google Routes, Kakao Local
│  ├─ static/
│  │  ├─ css/
│  │  └─ js/
│  └─ templates/            # Jinja2 HTML 템플릿
├─ alembic/
│  └─ versions/             # DB migration 파일
├─ tests/                   # pytest 자동 테스트
├─ .env.example             # 환경 변수 예시
├─ alembic.ini
├─ requirements.txt
└─ README.md
```

---

## 시작하기

### 1. 준비 사항

다음 프로그램이 설치되어 있어야 합니다.

- Python 3.11 이상 권장
- Git
- VS Code
- PowerShell

프로젝트를 내려받습니다.

```powershell
git clone <저장소_URL>
cd travel-agent
```

### 2. 가상환경 만들기

가상환경은 프로젝트마다 Python 패키지를 분리해서 관리하는 독립 공간입니다.

```powershell
python -m venv .venv
```

PowerShell에서 가상환경을 활성화합니다.

```powershell
.\.venv\Scripts\Activate.ps1
```

PowerShell 실행 정책 오류가 발생하면, 현재 터미널에서만 아래 명령을 실행한 뒤 다시 활성화하세요.

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

### 3. 패키지 설치

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 4. 환경 변수 파일 만들기

`.env.example`을 복사하여 `.env` 파일을 만듭니다.

```powershell
Copy-Item .\.env.example .\.env
```

이미 `.env` 파일이 있는 경우 덮어쓰지 마세요.

```powershell
Test-Path .\.env
```

`.env` 파일을 열어 필요한 값만 설정합니다.

```powershell
code .\.env
```

실제 API 키, 비밀번호, 토큰, SMTP 앱 비밀번호는 Git에 올리면 안 됩니다.

### 5. DB migration 적용

Alembic migration은 코드에 맞춰 SQLite 테이블과 컬럼 구조를 생성·업데이트하는 작업입니다.

```powershell
python -m alembic upgrade head
```

현재 DB migration 상태를 확인하려면 아래 명령을 사용합니다.

```powershell
python -m alembic current
python -m alembic heads
```

두 명령의 revision ID가 같으면 DB 구조가 최신 코드와 일치합니다.

> 다른 컴퓨터에서 `git pull`을 한 뒤 `alembic/versions/`에 새 파일이 있다면, `python -m alembic upgrade head`를 실행해야 합니다.

### 6. 개발 서버 실행

```powershell
python -m uvicorn app.main:app --reload
```

브라우저에서 아래 주소를 엽니다.

```text
http://127.0.0.1:8000
```

`--reload`는 Python 또는 템플릿 파일을 저장할 때 개발 서버를 자동으로 다시 시작하는 옵션입니다.

---

## 환경 변수

환경 변수 이름과 예시는 `.env.example`을 기준으로 확인하세요. 실제 값은 `.env`에만 저장합니다.

### 기본 설정

| 변수 | 설명 |
|---|---|
| `DATABASE_URL` | SQLite DB 연결 주소 |
| `SECRET_KEY` | 로그인 세션 서명용 비밀 키 |
| `SESSION_MAX_AGE_SECONDS` | 로그인 세션 유지 시간 |
| `APP_BASE_URL` | 비밀번호 재설정 링크 생성에 사용할 기본 URL |

### 이메일 설정

| 변수 | 설명 |
|---|---|
| `EMAIL_ENABLED` | 이메일 발송 활성화 여부 |
| `SMTP_HOST` | SMTP 서버 주소 |
| `SMTP_PORT` | SMTP 포트 |
| `SMTP_USERNAME` | SMTP 로그인 계정 |
| `SMTP_PASSWORD` | SMTP 앱 비밀번호 |
| `SMTP_FROM_EMAIL` | 발신 이메일 |
| `SMTP_FROM_NAME` | 발신자 표시 이름 |
| `SMTP_USE_TLS` | TLS 사용 여부 |

### 지도 및 AI 설정

| 변수 | 설명 |
|---|---|
| `GOOGLE_MAPS_API_KEY` | 서버에서 Google Places 및 Google Routes API 호출에 사용하는 키 |
| `GOOGLE_MAPS_BROWSER_API_KEY` | 브라우저에서 Google Maps JavaScript API를 로드하는 키 |
| `KAKAO_REST_API_KEY` | Kakao Local API 검색에 사용하는 REST API 키 |
| `GEMINI_API_KEY` | Gemini API 호출에 사용하는 키 |

### 키 보안 권장 사항

- `GOOGLE_MAPS_API_KEY`와 `GOOGLE_MAPS_BROWSER_API_KEY`는 분리합니다.
- 서버용 Google 키는 Places API (New), Routes API만 허용하도록 제한합니다.
- 브라우저용 Google 키는 Maps JavaScript API만 허용하고, HTTP 리퍼러 제한을 적용합니다.
- `.env`와 SQLite DB 파일은 Git에 커밋하지 않습니다.
- API 키가 노출되었다면 즉시 해당 키를 폐기하고 새 키를 발급합니다.

---

## 외부 API 설정

일부 기능은 관련 API가 활성화되고 키가 설정되어야 동작합니다.

| 기능 | 필요한 API 또는 설정 |
|---|---|
| 해외 장소 검색 | Google Places API (New) |
| 통합 지도 | Google Maps JavaScript API |
| AI 코스 장소 수집 | Google Places API (New) |
| AI 도보 동선 | Google Routes API |
| 국내 장소 검색 | Kakao Local API |
| AI 코스 초안 | Gemini API |
| 예약 스크린샷 분석 | Gemini API |
| 비밀번호 재설정 메일 | SMTP 설정 및 `EMAIL_ENABLED=true` |

Google API 사용량과 Gemini API 사용량에는 비용 또는 무료 할당량 제한이 적용될 수 있습니다. 개발·배포 전에 각 API 콘솔의 사용량, 예산 알림, 키 제한 설정을 확인하세요.

---

## 테스트

가상환경을 활성화한 상태에서 실행합니다.

```powershell
.\.venv\Scripts\pytest.exe tests\test_pages.py -q
.\.venv\Scripts\pytest.exe -q
```

변경 파일에 공백 오류가 없는지 확인합니다.

```powershell
git diff --check
```

현재 테스트는 인증, 여행, 구성원 초대·권한, 일정 CRUD·충돌 처리, 장소 후보, 장소 검색, AI 코스 초안, 도보 동선, 예약 가져오기, 페이지 마크업 등을 검증합니다.

---

## 개발 시 작업 순서

다른 컴퓨터에서 개발을 이어갈 때는 아래 순서를 권장합니다.

```powershell
git pull --ff-only
python -m alembic upgrade head
python -m uvicorn app.main:app --reload
```

작업이 끝난 뒤에는 변경 내용을 확인합니다.

```powershell
git status
git diff --check
.\.venv\Scripts\pytest.exe -q
```

`.env`, `travelplanner.db`, 가상환경 폴더, 개인용 Gitingest 결과 파일은 커밋하지 마세요.

---

## 현재 제한 사항

- AI 코스 초안은 새로고침하면 사라지는 브라우저 임시 상태입니다.
- 기존에 좌표 없이 저장된 일정은 지도 마커로 자동 표시되지 않습니다.
- 교통 일정은 출발지와 도착지를 하나의 단일 좌표로 저장하지 않으므로, 기본적으로 지도 마커 대상이 아닙니다.
- 지도·장소 검색·AI·도보 동선은 외부 API 상태, 키 제한, 사용량 제한에 영향을 받습니다.
- 예약 정보 추출 결과는 AI 분석 결과이므로, 실제 예약 정보와 시간을 사용자가 반드시 확인해야 합니다.
- 외부 예약 페이지를 직접 크롤링해 자동으로 정보를 읽는 기능은 구현하지 않았습니다.

---

## 향후 계획

- 기존 일정에 장소 검색 결과를 연결하는 기능
- 교통 일정의 출발·도착 위치 및 이동 경로 표시
- AI 코스 초안의 저장·공유·재편집
- 일정 마커와 일정 카드의 상호 강조 및 스크롤 이동
- 일정 순서 드래그 정렬과 이동 시간 기반 충돌 안내
- 예약 정보의 구조화 및 확인 상태 관리
- 배포 환경 설정 및 운영용 보안·백업 정책
- 모바일 UI와 접근성 세부 개선

---

## 보안 및 개인정보

- `.env`, API 키, 토큰, SMTP 앱 비밀번호를 커밋하거나 공유하지 마세요.
- 실제 사용자 이메일, 예약번호, 항공권·숙소 정보, 결제 정보는 테스트 데이터로 사용하지 않는 것이 좋습니다.
- 공유 여행에서는 구성원이 볼 수 있는 장소 메모·예약 링크에 개인정보가 포함되지 않도록 주의하세요.
- 운영 환경에서는 HTTPS, 강한 `SECRET_KEY`, 제한된 CORS 정책, API 키 제한, DB 백업 정책을 별도로 적용해야 합니다.

---

## 라이선스

학습 및 개인 프로젝트 용도로 사용 중입니다. 배포 또는 상업적 사용 전에는 사용하는 외부 API와 라이브러리의 약관 및 라이선스를 확인하세요.