# AE-Nexrender Module - 테스트 환경

CyprusDesign.aep 템플릿을 활용한 렌더링 테스트 환경입니다.

## 파일 구조

```
ae_nexrender_module/
├── tests/
│   ├── __init__.py
│   └── sample_data.py          # 샘플 GFX 데이터 생성기
├── scripts/
│   ├── __init__.py
│   ├── test_render.py          # 단일 렌더링 테스트 CLI
│   └── seed_render_queue.py    # Supabase 시딩 스크립트
├── lib/                         # 핵심 라이브러리
│   ├── client.py               # NexrenderClient
│   ├── job_builder.py          # NexrenderJobBuilder
│   └── ...
└── worker/                      # 렌더링 워커
    └── ...
```

## 1. 샘플 데이터 생성기 (tests/sample_data.py)

CyprusDesign.aep의 5가지 컴포지션 타입을 지원합니다.

### 지원 컴포지션

1. `1-Hand-for-hand play is currently in progress` (단일 필드만)
2. `1-NEXT STREAM STARTING SOON` (단일 필드만)
3. `2-Hand-for-hand play is currently in progress` (단일 필드 + 2개 슬롯)
4. `2-NEXT STREAM STARTING SOON` (단일 필드 + 2개 슬롯)
5. `4-NEXT STREAM STARTING SOON` (단일 필드 + 4개 슬롯)

### 사용 예시

```python
from tests.sample_data import (
    generate_sample_gfx_data,
    generate_sample_render_request,
    generate_batch_render_requests,
)

# 1. 단일 GFX 데이터 생성
gfx_data = generate_sample_gfx_data("1-Hand-for-hand play is currently in progress")
print(gfx_data)
# {
#     "slots": [],
#     "single_fields": {
#         "event_name": "EVENT #12: ...",
#         "message": "Hand-for-hand...",
#         "table_id": "Table 1"
#     }
# }

# 2. render_queue INSERT용 데이터 생성
# [필수] 기본값: mov_alpha (투명 배경)
render_request = generate_sample_render_request(
    composition_name="2-NEXT STREAM STARTING SOON",
    output_format="mov_alpha",  # 기본값 - 투명 배경 필수
    priority=5,
)

# 3. 배치 작업 생성 (5개)
batch_requests = generate_batch_render_requests(count=5)
```

## 2. 단일 렌더링 테스트 (scripts/test_render.py)

Nexrender Job JSON 생성 및 렌더링을 테스트합니다.

### 사용법

```bash
# 샘플 데이터로 Job JSON 확인 (Dry-run)
python scripts/test_render.py --sample --dry-run

# 실제 렌더링 실행
python scripts/test_render.py --sample

# 특정 컴포지션 테스트
python scripts/test_render.py --composition "1-Hand-for-hand play is currently in progress"

# 진행률 폴링 없이 빠른 제출
python scripts/test_render.py --sample --no-poll

# 커스텀 출력 설정
python scripts/test_render.py --sample \
  --output-format mov \
  --output-filename custom_output
```

### 주요 옵션

| 옵션 | 설명 |
|------|------|
| `--sample` | 첫 번째 샘플 컴포지션 사용 |
| `--composition` | 특정 컴포지션 선택 |
| `--dry-run` | Job JSON만 생성 (렌더링 안함) |
| `--no-poll` | 진행률 폴링 건너뜀 |
| `--output-format` | 출력 포맷 (기본: **mov_alpha**, mov, mp4, png_sequence) |
| `--field` | 필드 값 오버라이드 (예: `--field event_name="MY EVENT"`) |

### 출력 포맷 상세

> **[CRITICAL] 기본 출력 포맷은 `mov_alpha`입니다. 다른 포맷은 명시적 요청 시에만 사용하세요.**

| 포맷 | 확장자 | 설명 | Output Module |
|------|--------|------|---------------|
| **`mov_alpha`** | .mov | **[기본값]** 알파 채널 포함 (투명 배경) | Alpha MOV |
| `mov` | .mov | QuickTime 무손실 | AE 기본 설정 |
| `mp4` | .mp4 | H.264 압축 | AE 기본 설정 |
| `png_sequence` | .png | PNG 시퀀스 | AE 기본 설정 |

### 알파 채널 출력 (mov_alpha)

투명 배경이 필요한 그래픽 오버레이 렌더링 시 사용합니다.

```bash
# 알파 채널 mov 렌더링
python scripts/test_render.py --sample \
  --output-format mov_alpha \
  --field event_name="WSOP 2026" \
  --field message="Tournament Starting"

# 생성되는 Job JSON의 template 섹션:
# {
#   "src": "file:///...",
#   "composition": "...",
#   "outputModule": "Apple ProRes 4444",  <-- 핵심 설정
#   "outputExt": "mov"
# }
```

**주의사항**:
- **AE 프로젝트에서 렌더 설정이 알파 채널을 지원하는 코덱으로 설정되어 있어야 합니다**
- 현재 CyprusDesign.aep는 H.264 (mp4)로 설정되어 있어 mov_alpha 사용 시 AE 프로젝트 수정 필요
- 파일 크기가 mp4보다 훨씬 큽니다 (무손실 + 알파 채널)
- 방송 송출용 오버레이에 적합합니다

**AE 프로젝트 알파 출력 설정 방법**:
1. After Effects에서 프로젝트 열기
2. Composition > Add to Render Queue
3. Output Module 클릭 > Format: QuickTime
4. Format Options > Video Codec: Animation 또는 ProRes 4444
5. Channels: RGB + Alpha
6. 템플릿으로 저장 후 프로젝트 저장

## 3. Supabase 시딩 (scripts/seed_render_queue.py)

render_queue 테이블에 테스트 작업을 삽입합니다.

### 전제조건

```bash
# .env 파일 설정
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_KEY=eyJxxx
```

### 사용법

```bash
# 5개 랜덤 작업 생성
python scripts/seed_render_queue.py --count 5

# 모든 컴포지션 타입 생성 (5개)
python scripts/seed_render_queue.py --all

# 특정 컴포지션만 생성
python scripts/seed_render_queue.py --composition "1-Hand-for-hand play is currently in progress"

# 상세 출력 (GFX 데이터 포함)
python scripts/seed_render_queue.py --count 3 --verbose

# 우선순위 및 출력 포맷 커스터마이징
python scripts/seed_render_queue.py --count 5 --priority 8 --output-format mov
```

### 주요 옵션

| 옵션 | 설명 |
|------|------|
| `--count N` | N개 랜덤 작업 생성 |
| `--all` | 모든 컴포지션 타입 생성 (5개) |
| `--composition` | 특정 컴포지션만 생성 |
| `--verbose` | GFX 데이터 상세 출력 |
| `--priority` | 우선순위 (1-10) |

## 4. E2E 테스트 워크플로우

### Step 1: 환경 설정

```bash
# .env 파일 생성 (예시는 .env.example 참고)
cp .env.example .env
vim .env

# 필수 환경변수:
# - SUPABASE_URL
# - SUPABASE_SERVICE_KEY
# - NEXRENDER_URL (기본: http://localhost:3000)
# - OUTPUT_DIR_HOST (기본: D:/output)
```

### Step 2: Nexrender 서버 실행

```bash
# Nexrender 서버가 실행 중인지 확인
curl http://localhost:3000/api/v1/jobs
```

### Step 3: Dry-run 테스트

```bash
# Job JSON 생성 확인
python scripts/test_render.py --sample --dry-run
```

출력 예시:

```json
{
  "template": {
    "src": "file:///C:/claude/automation_ae/templates/CyprusDesign/CyprusDesign.aep",
    "composition": "1-Hand-for-hand play is currently in progress",
    "continueOnMissing": true,
    "outputExt": "mp4"
  },
  "assets": [
    {
      "type": "data",
      "layerName": "event_name",
      "property": "Source Text",
      "value": "EVENT #12: $5,000 MEGA MYSTERY BOUNTY RAFFLE"
    },
    ...
  ],
  "actions": {
    "postrender": [...]
  }
}
```

### Step 4: 단일 렌더링 테스트

```bash
# 실제 렌더링 실행
python scripts/test_render.py --sample

# 진행률 폴링 예시:
# [RENDERING] Progress: 45%
# [ENCODING] Progress: 85%
# [FINISHED] Progress: 100%
```

### Step 5: Supabase 시딩

```bash
# render_queue에 5개 작업 생성
python scripts/seed_render_queue.py --count 5

# 출력 예시:
# [Seed] 삽입 성공: abc12345... (1-Hand-for-hand play...)
# [Seed] 삽입 성공: def67890... (2-NEXT STREAM STARTING SOON...)
# ...
```

### Step 6: Worker 실행 및 모니터링

```bash
# Worker 실행
python -m worker.main

# 로그 확인:
# [Worker] 작업 할당: Job abc12345
# [Processor] Nexrender Job Data 생성
# [Processor] Nexrender 작업 제출: UID=xyz123
# [Processor] 진행률 폴링...
# [Processor] 작업 완료: output=D:/output/test_render.mp4
```

### Step 7: Supabase 대시보드 확인

1. Supabase 대시보드 접속
2. `render_queue` 테이블 열기
3. 상태 변화 확인:
   - `pending` → `preparing` → `rendering` → `completed`

## 5. 문제 해결

### Nexrender 서버 연결 실패

```
Error: Nexrender 서버 연결 실패: http://localhost:3000
```

**해결:**
- Nexrender 서버가 실행 중인지 확인
- `NEXRENDER_URL` 환경변수 확인
- 방화벽 설정 확인

### Supabase 연결 실패

```
Error: SUPABASE_URL 환경변수가 설정되지 않았습니다.
```

**해결:**
- `.env` 파일에 `SUPABASE_URL`, `SUPABASE_SERVICE_KEY` 설정
- 또는 CLI 옵션으로 직접 전달: `--supabase-url`, `--supabase-key`

### AEP 파일 경로 오류

```
Error: AEP 파일을 찾을 수 없습니다.
```

**해결:**
- `--aep-path` 옵션으로 경로 확인
- 기본 경로: `C:/claude/automation_ae/templates/CyprusDesign/CyprusDesign.aep`

## 6. 다음 단계

### 통합 테스트

```bash
# 1. Worker 실행
python -m worker.main &

# 2. 작업 시딩
python scripts/seed_render_queue.py --all

# 3. 로그 모니터링
tail -f worker.log
```

### 성능 테스트

```bash
# 100개 작업 생성
python scripts/seed_render_queue.py --count 100

# 여러 Worker 실행 (병렬 처리)
python -m worker.main &  # Worker 1
python -m worker.main &  # Worker 2
python -m worker.main &  # Worker 3
```

### 커스텀 컴포지션 추가

`tests/sample_data.py`의 `COMPOSITION_LAYERS`에 새 컴포지션 추가:

```python
COMPOSITION_LAYERS = {
    # 기존 컴포지션...
    "새_컴포지션_이름": {
        "single_fields": {
            "field1": "default_value",
            "field2": "default_value",
        },
        "slots": [
            {"slot_index": 1, "field_names": ["name", "chips"]},
        ],
    },
}
```

## 참고

- **Worker 코드**: `C:\claude\ae_nexrender_module\worker\`
- **라이브러리**: `C:\claude\ae_nexrender_module\lib\`
- **마이그레이션**: `C:\claude\ae_nexrender_module\migrations\`
- **Docker 설정**: `C:\claude\ae_nexrender_module\docker\`
