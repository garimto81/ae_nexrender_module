# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## **[CRITICAL] 출력 포맷 필수 규칙**

| 규칙 | 내용 | 위반 시 |
|:----:|------|--------|
| **기본 출력** | `mov_alpha` (투명 배경) | **절대 금지** |
| **Output Module** | `Alpha MOV` | **필수 설정** |
| **mp4 사용** | 명시적 요청 시에만 | 확인 필요 |

### 강제 사항

1. **모든 렌더링의 기본 출력 포맷은 `mov_alpha`입니다.**
2. **mp4, mov 등 다른 포맷은 사용자가 명시적으로 요청한 경우에만 사용합니다.**
3. **테스트 렌더링도 예외 없이 `mov_alpha`를 사용합니다.**

### 올바른 예

```powershell
# 기본 렌더링 (mov_alpha)
python scripts/test_render.py --sample

# 명시적으로 mp4 요청 시에만
python scripts/test_render.py --sample --output-format mp4
```

### 잘못된 예

```powershell
# ❌ mp4를 기본값처럼 사용
python scripts/test_render.py --sample --output-format mp4  # 사용자 요청 없이
```

---

## Project Overview

**ae-nexrender-module**은 After Effects 렌더링 자동화를 위한 독립 워커 서비스입니다. Supabase `render_queue`를 폴링하여 Nexrender 서버에 렌더링 작업을 제출하고 진행률을 추적합니다.

## Architecture

```
lib/                    # 공통 라이브러리 (nexrender_core)
├── client.py           # NexrenderClient (비동기/동기 API 클라이언트)
├── job_builder.py      # Nexrender Job JSON 빌더 (GFX Data → Job JSON)
├── path_utils.py       # Docker ↔ Windows 경로 변환
├── mapping_loader.py   # GFX 필드명 → AEP 레이어명 매핑
├── errors.py           # 에러 분류 시스템 (retryable/non_retryable)
└── types.py            # 공용 타입 정의

worker/                 # 폴링 기반 비동기 워커
├── main.py             # 워커 엔트리포인트 (적응형 폴링 루프)
├── job_processor.py    # 5단계 렌더링 처리 (claim → submit → poll → postprocess → complete)
├── supabase_client.py  # Supabase render_queue CRUD
├── config.py           # 환경변수 기반 설정
└── health.py           # 헬스체크 HTTP 서버

api/                    # FastAPI REST API (선택적)
├── server.py           # FastAPI 앱 정의
├── routes/             # 라우터 (health, render, config)
├── schemas/            # Pydantic 스키마
└── middleware/         # 인증 미들웨어

config/                 # 설정 파일
├── api_config.yaml     # API 서버 및 템플릿 설정 (핫 리로드 지원)
└── mappings/           # 템플릿별 레이어 매핑 YAML
```

## Data Flow

```
Dashboard (Next.js) → Supabase render_queue (INSERT)
                              ↓
                      Worker (Polling) → claim_render_job RPC
                              ↓
                      NexrenderJobBuilder → Job JSON 생성
                              ↓
                      NexrenderClient → Nexrender 서버 제출
                              ↓
                      진행률 폴링 → 상태 업데이트
                              ↓
                      render_queue (UPDATE: completed/failed)
```

## Commands

### Development

```powershell
# Python 테스트 실행
pytest tests/ -v

# 개별 테스트
pytest tests/test_job_builder.py -v
pytest tests/test_path_utils.py -v

# 린트
ruff check lib/ worker/ api/ --fix

# 타입 체크
mypy lib/ worker/
```

### Worker 실행

```powershell
# 환경변수 설정 후 워커 실행
python -m worker.main

# 또는 스크립트로 실행
python scripts/render_worker.py
```

### Nexrender 서버 (Node.js)

```powershell
# 서버 + 워커 동시 실행
npm start

# 서버만 실행 (포트 3030)
npm run server

# Nexrender 워커만 실행
npm run worker
```

### API 서버 (선택적)

```powershell
# FastAPI 서버 실행
python -m api.server
# 또는
uvicorn api.server:app --host 0.0.0.0 --port 8000 --reload

# API 스크립트
python scripts/render_api_server.py
```

### 테스트 렌더링

```powershell
# Dry-run (Job JSON만 생성)
python scripts/test_render.py --sample --dry-run

# 실제 렌더링 실행
python scripts/test_render.py --sample

# 특정 컴포지션 테스트
python scripts/test_render.py --composition "1-Hand-for-hand play is currently in progress"

# 알파 채널 MOV 렌더링
python scripts/test_render.py --sample --output-format mov_alpha
```

### Supabase 시딩

```powershell
# 테스트 작업 5개 생성
python scripts/seed_render_queue.py --count 5

# 모든 컴포지션 타입 생성
python scripts/seed_render_queue.py --all
```

## Key Concepts

### GFX Data 구조

```python
{
    "slots": [
        {"slot_index": 1, "fields": {"name": "PHIL IVEY", "chips": "250,000"}}
    ],
    "single_fields": {"table_id": "Table 1", "event_name": "EVENT #12"}
}
```

### 레이어 매핑

GFX 필드명과 AEP 레이어명이 다를 경우 `config/mappings/{template}.yaml`에서 매핑 정의. 매핑이 없으면 GFX 필드명을 그대로 `layerName`으로 사용.

### Alpha MOV 출력

`output_format: "mov_alpha"` 사용 시:
- `outputModule: "Alpha MOV"` 설정 (AE 프로젝트에 템플릿 필요)
- 배경 레이어 자동 비활성화 JSX 스크립트 주입

### 에러 분류

`lib/errors.py`의 `ErrorClassifier`가 에러를 분류:
- `RETRYABLE`: 네트워크 오류, 일시적 장애 → 자동 재시도
- `NON_RETRYABLE`: 설정 오류, 파일 없음 → 즉시 실패

### 경로 변환

Docker 내부 경로(`/app/templates/...`) → Windows 경로(`C:/templates/...`) 자동 변환. `PathConverter` 클래스가 `file://` URL로 변환하여 Nexrender에 전달.

## Environment Variables

`.env` 파일 또는 환경변수로 설정:

```bash
# 필수
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_KEY=eyJxxx

# Nexrender
NEXRENDER_URL=http://localhost:3000
NEXRENDER_SECRET=

# 경로
OUTPUT_DIR_HOST=D:/output
TEMPLATE_DIR_HOST=D:/templates

# API 서버 (선택)
API_PORT=8000
API_KEYS=your-api-key
```

## Testing Fixtures

`tests/conftest.py`에 정의된 주요 fixture:
- `sample_gfx_data`: 기본 GFX 데이터
- `sample_gfx_data_multi_slot`: 여러 슬롯 포함
- `worker_config`: 테스트용 WorkerConfig
- `path_converter`: 테스트용 PathConverter

---

## [필수] 새 컴포지션 추가 시 워크플로우

**PRD 14절 참조**: `tasks/prds/PRD-0011-ae-nexrender-v2.md`

```
Step 1: AEP 분석 파일에서 실제 레이어명 확인
───────────────────────────────────────────────
$ cat CyprusDesign_analysis.json | jq '.compositions["컴포지션명"]'

Step 2: YAML 매핑 파일 작성
───────────────────────────────────────────────
$ vim config/mappings/CyprusDesign.yaml

⚠️ 주의: AEP 분석 결과의 실제 레이어명 사용
❌ slot1_name: "SLOT1_NAME"   # 추측 금지
✅ slot1_name: "Name 1"       # 분석 결과 사용

Step 3: sample_data.py 슬롯 수 동기화
───────────────────────────────────────────────
$ vim tests/sample_data.py
# range(1, N+1) → N = 실제 AEP 레이어 개수

Step 4: Dry-Run 검증
───────────────────────────────────────────────
$ python scripts/test_render.py --composition "컴포지션명" --dry-run
# "layerName": "Name 1" 확인 (AEP 레이어명과 일치)

Step 5: 실제 렌더링 테스트
───────────────────────────────────────────────
$ python scripts/test_render.py --composition "컴포지션명"
```

### 트러블슈팅: 이름이 변경되지 않음

| 증상 | 원인 | 해결 |
|------|------|------|
| 텍스트 기본값 유지 | 레이어명 불일치 | AEP 분석 후 YAML 수정 |
| 일부만 변경됨 | 매핑 누락 | YAML에 필드 추가 |
| 슬롯 일부만 변경 | 슬롯 수 불일치 | sample_data.py 수정 |

**진단**:
```powershell
# Job JSON에서 layerName 확인
python scripts/test_render.py --composition "컴포지션명" --dry-run | grep layerName
```
