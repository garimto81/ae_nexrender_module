# PRD-0011: ae-nexrender 렌더링 워커 모듈 v2

**문서 버전**: 2.2
**상태**: In Progress
**작성일**: 2026-01-15
**최종 수정일**: 2026-01-19
**담당자**: Backend Team

---

## 1. 개요 (Overview)

### 1.1 목적

ae-nexrender는 **automation_ae 대시보드에서 분리된 독립 렌더링 워커 서비스**입니다. 대시보드는 Supabase `render_queue` 테이블에 렌더링 요청을 추가하고, ae-nexrender 워커가 폴링 방식으로 작업을 처리합니다.

### 1.2 v1 대비 주요 변경사항

| 항목 | v1 (기존) | v2 (개선) |
|------|----------|----------|
| **데이터베이스** | PostgreSQL + Redis | Supabase Cloud |
| **작업 큐** | Celery | 폴링 기반 워커 |
| **코드 구조** | 단일 서비스 | 공통 라이브러리 (lib/) 분리 |
| **인프라** | Docker 3개 컨테이너 | Docker 워커만 |
| **상태 관리** | 로컬 DB | Supabase Realtime |

### 1.3 주요 기능

| 기능 | 설명 |
|------|------|
| **렌더링 작업 폴링** | Supabase render_queue 테이블에서 대기 작업 조회 |
| **Nexrender 작업 제출** | 워커가 Nexrender에 렌더링 작업 제출 |
| **진행률 모니터링** | Nexrender 폴링 또는 Webhook을 통한 실시간 진행률 추적 |
| **재시도 로직** | 에러 분류 기반 자동 재시도 (재시도 가능 에러만) |
| **락 메커니즘** | 다중 워커 환경에서 작업 충돌 방지 |
| **Crash Recovery** | 워커 크래시 시 30분 후 자동 작업 복구 |
| **Alpha MOV 출력** | **[필수 기본값]** 투명 배경 MOV 렌더링 (QuickTime Animation + RGB+Alpha) |
| **배경 레이어 비활성화** | mov_alpha 모드 시 자동 배경 레이어 숨김 |

### 1.4 [CRITICAL] 출력 포맷 필수 규칙

| 규칙 | 내용 | 위반 시 |
|:----:|------|--------|
| **기본 출력** | `mov_alpha` (투명 배경) | **절대 금지** |
| **Output Module** | `Alpha MOV` | **필수 설정** |
| **mp4 사용** | 명시적 요청 시에만 | 사전 확인 필요 |

**강제 사항**:
1. 모든 렌더링의 기본 출력 포맷은 `mov_alpha`입니다.
2. `mp4`, `mov` 등 다른 포맷은 사용자가 명시적으로 요청한 경우에만 사용합니다.
3. 테스트 렌더링도 예외 없이 `mov_alpha`를 사용합니다.
4. DB 스키마의 기본값도 `mov_alpha`입니다.

### 1.5 기술 스택

- **Worker**: Python 3.11+ (asyncio)
- **Database**: Supabase (PostgreSQL + Realtime)
- **Nexrender**: Node.js (localhost:3000)
- **Container**: Docker (선택)

---

## 2. 목표 (Goals)

### 2.1 기술 목표

| 목표 | 성공 지표 |
|------|---------|
| 렌더링 작업 분리 | 대시보드와 워커 서비스 완전 분리 |
| 높은 가용성 | 재시도 정책으로 95% 성공률 달성 |
| 스케일링 | 여러 워커 인스턴스 동시 실행 가능 |
| 코드 재사용 | automation_ae와 공통 라이브러리 공유 |
| 인프라 단순화 | Supabase로 Redis/PostgreSQL 제거 |

### 2.2 비즈니스 목표

- 대시보드 부하 감소로 응답 속도 개선
- 인프라 비용 절감 (Celery/Redis 제거)
- 향후 멀티 워커 배포 기반 마련

---

## 3. 비목표 (Non-Goals)

| 항목 | 이유 |
|------|------|
| GPU 렌더링 최적화 | Nexrender의 기본 CPU 렌더링으로 충분 |
| REST API 서버 | Supabase Direct 접근으로 대체 |
| 웹 UI 제공 | 대시보드에서만 조작 |
| 파일 업로드/다운로드 | Nexrender이 직접 처리 |

---

## 4. 시스템 아키텍처

### 4.1 전체 아키텍처

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    ae_nexrender_module 아키텍처                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌─────────────────┐                                                       │
│   │  lib/           │  ← 공통 라이브러리 (nexrender_core)                  │
│   ├─────────────────┤                                                       │
│   │ - client.py     │  비동기/동기 Nexrender API 클라이언트               │
│   │ - job_builder.py│  Job JSON 빌더 (Template/GFX 방식)                  │
│   │ - path_utils.py │  Docker↔Windows 경로 변환                           │
│   │ - errors.py     │  에러 분류 시스템                                    │
│   │ - types.py      │  공용 타입/스키마                                    │
│   └─────────────────┘                                                       │
│          │                                                                   │
│          ▼                                                                   │
│   ┌─────────────────┐    ┌─────────────────┐                               │
│   │  Worker         │    │  Supabase       │                               │
│   │  (worker/)      │◄──▶│  render_queue   │                               │
│   ├─────────────────┤    └─────────────────┘                               │
│   │ - main.py       │         │                                             │
│   │ - job_processor │         │ Realtime/Polling                           │
│   │ - health.py     │         ▼                                             │
│   └─────────────────┘    ┌─────────────────┐                               │
│          │               │  Nexrender      │                               │
│          └──────────────▶│  Server (Local) │                               │
│                          └─────────────────┘                               │
│                                │                                            │
│                                ▼                                            │
│                          ┌─────────────────┐                               │
│                          │  NAS Output     │                               │
│                          │  (\\nas\renders)│                               │
│                          └─────────────────┘                               │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 데이터 흐름

```
┌─────────────────┐
│  Sub Dashboard  │
│  (Next.js)      │
└────────┬────────┘
         │ INSERT
         ▼
┌─────────────────┐     ┌─────────────────┐
│  Supabase       │     │  AE-Worker      │
│  render_queue   │◄────│  (Polling)      │
│  (pending)      │     └────────┬────────┘
└─────────────────┘              │
         │                       │ Claim (preparing)
         │                       ▼
         │              ┌─────────────────┐
         │              │  Nexrender      │
         │              │  Job JSON 생성  │
         │              └────────┬────────┘
         │                       │ Submit
         │                       ▼
         │              ┌─────────────────┐
         │              │  Nexrender      │
         │              │  Server         │
         │              │  (렌더링 실행)  │
         │              └────────┬────────┘
         │                       │ Poll Progress
         │                       ▼
         │              ┌─────────────────┐
         │              │  완료 후처리    │
         │              │  - NAS 복사     │
         │              │  - 상태 업데이트│
         │              └────────┬────────┘
         │                       │
         ▼ UPDATE (completed)    │
┌─────────────────┐              │
│  render_queue   │◄─────────────┘
│  (completed)    │
└─────────────────┘
```

### 4.3 디렉토리 구조

```
C:\claude\ae_nexrender_module\
├── lib/                          # 공통 라이브러리 (nexrender_core)
│   ├── __init__.py
│   ├── client.py                 # NexrenderClient (비동기/동기)
│   ├── job_builder.py            # NexrenderJobBuilder
│   ├── gfx_slot_builder.py       # GFX Slot → Nexrender Assets
│   ├── path_utils.py             # 경로 변환 유틸리티
│   ├── errors.py                 # 에러 분류 시스템
│   └── types.py                  # 공용 타입 정의
│
├── worker/                       # 폴링 기반 워커
│   ├── __init__.py
│   ├── main.py                   # 워커 엔트리포인트
│   ├── job_processor.py          # 작업 처리 로직
│   ├── supabase_client.py        # Supabase 연동
│   ├── health.py                 # 헬스체크
│   └── config.py                 # 워커 설정
│
├── migrations/                   # Supabase 마이그레이션
│   ├── 001_render_queue.sql
│   └── 002_rpc_functions.sql
│
├── tests/                        # 테스트
│   ├── test_client.py
│   ├── test_job_builder.py
│   └── test_worker.py
│
├── docker/                       # Docker 설정
│   ├── Dockerfile
│   └── docker-compose.yml
│
├── tasks/
│   └── prds/
│       └── PRD-0011-ae-nexrender-v2.md
│
└── pyproject.toml               # 패키지 설정
```

---

## 5. Supabase 스키마

### 5.1 render_queue 테이블

```sql
-- ============================================================================
-- render_queue: Supabase 렌더링 작업 큐
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.render_queue (
    -- 기본 식별자
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- 작업 구성
    composition_id UUID REFERENCES public.aep_compositions(id),
    composition_name TEXT NOT NULL,
    aep_project_path TEXT NOT NULL,

    -- 렌더링 데이터 (gfx_data JSON)
    gfx_data JSONB NOT NULL,

    -- 출력 설정
    -- [필수] 기본값: mov_alpha (투명 배경) - 모든 렌더링은 mov_alpha가 기본
    output_format TEXT DEFAULT 'mov_alpha' CHECK (output_format IN ('mov_alpha', 'mov', 'mp4', 'png_sequence')),
    output_dir TEXT,
    output_filename TEXT,

    -- 상태 관리
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'preparing', 'rendering', 'encoding', 'uploading', 'completed', 'failed', 'cancelled')),
    progress INTEGER DEFAULT 0 CHECK (progress >= 0 AND progress <= 100),

    -- Nexrender 연동
    nexrender_job_id TEXT,
    nexrender_state TEXT,

    -- 워커 할당
    worker_id UUID,
    lock_expires_at TIMESTAMPTZ,

    -- 에러 처리
    error_message TEXT,
    error_category TEXT CHECK (error_category IN ('retryable', 'non_retryable', 'unknown')),
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    recovery_count INTEGER DEFAULT 0,

    -- 콜백 URL (Webhook 모드)
    callback_url TEXT,

    -- 출력 결과
    output_file_path TEXT,
    output_file_size BIGINT,
    duration_seconds REAL,

    -- 연관 데이터
    cue_item_id UUID,
    source_system TEXT CHECK (source_system IN ('dashboard', 'api', 'cuesheet')),

    -- 우선순위
    priority INTEGER DEFAULT 5 CHECK (priority >= 1 AND priority <= 10),

    -- 타임스탬프
    created_at TIMESTAMPTZ DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 인덱스
CREATE INDEX idx_render_queue_status ON public.render_queue(status);
CREATE INDEX idx_render_queue_worker ON public.render_queue(worker_id);
CREATE INDEX idx_render_queue_created ON public.render_queue(created_at);
CREATE INDEX idx_render_queue_priority_status ON public.render_queue(priority DESC, status, created_at ASC);

-- Updated At 트리거
CREATE OR REPLACE FUNCTION update_render_queue_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_render_queue_updated_at
BEFORE UPDATE ON public.render_queue
FOR EACH ROW
EXECUTE FUNCTION update_render_queue_updated_at();
```

### 5.2 render_queue_audit 테이블 (선택)

```sql
-- ============================================================================
-- render_queue_audit: 상태 변경 감사 로그
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.render_queue_audit (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    render_queue_id UUID REFERENCES public.render_queue(id) ON DELETE CASCADE,
    status_from TEXT,
    status_to TEXT,
    worker_id UUID,
    changed_at TIMESTAMPTZ DEFAULT NOW(),
    changed_by TEXT,
    details JSONB
);

CREATE INDEX idx_render_queue_audit_queue ON public.render_queue_audit(render_queue_id);
```

### 5.3 RLS 정책

```sql
-- ============================================================================
-- Row Level Security 정책
-- ============================================================================

-- RLS 활성화
ALTER TABLE public.render_queue ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.render_queue_audit ENABLE ROW LEVEL SECURITY;

-- 서비스 역할 (모든 권한)
CREATE POLICY "service_role_all" ON public.render_queue
    FOR ALL USING (auth.jwt()->>'role' = 'service_role');

-- 워커 (자신의 작업만)
CREATE POLICY "worker_select_pending" ON public.render_queue
    FOR SELECT USING (
        status = 'pending' OR worker_id = (auth.jwt()->>'worker_id')::UUID
    );

CREATE POLICY "worker_update_own" ON public.render_queue
    FOR UPDATE USING (
        worker_id = (auth.jwt()->>'worker_id')::UUID
    );

-- 대시보드 (읽기 + INSERT)
CREATE POLICY "dashboard_read" ON public.render_queue
    FOR SELECT USING (auth.jwt()->>'role' = 'authenticated');

CREATE POLICY "dashboard_insert" ON public.render_queue
    FOR INSERT WITH CHECK (auth.jwt()->>'role' = 'authenticated');
```

### 5.4 RPC 함수 - claim_render_job

```sql
-- ============================================================================
-- claim_render_job: Atomic 작업 할당 함수
-- ============================================================================
CREATE OR REPLACE FUNCTION claim_render_job(
    p_worker_id UUID,
    p_lock_expires_at TIMESTAMPTZ
)
RETURNS SETOF render_queue
LANGUAGE plpgsql
AS $$
DECLARE
    claimed_job render_queue;
BEGIN
    -- Atomic UPDATE ... RETURNING
    UPDATE render_queue
    SET status = 'preparing',
        worker_id = p_worker_id,
        lock_expires_at = p_lock_expires_at,
        started_at = NOW(),
        updated_at = NOW()
    WHERE id = (
        SELECT id FROM render_queue
        WHERE status = 'pending'
          OR (status IN ('preparing', 'rendering')
              AND lock_expires_at < NOW())  -- Crash Recovery
        ORDER BY priority DESC, created_at ASC
        LIMIT 1
        FOR UPDATE SKIP LOCKED
    )
    RETURNING * INTO claimed_job;

    IF FOUND THEN
        RETURN NEXT claimed_job;
    END IF;
END;
$$;
```

### 5.5 지원 컴포지션 목록

| 컴포지션 이름 | 슬롯 수 | 필드 | 설명 |
|--------------|:------:|------|------|
| `1-Hand-for-hand play is currently in progress` | 0 | event_name, message, table_id | 핸드-바이-핸드 단일 필드 |
| `1-NEXT STREAM STARTING SOON` | 0 | event_name, tournament_name | 스트림 시작 안내 |
| `2-Hand-for-hand play is currently in progress` | 2 | event_name, message, table_id + slots | 핸드-바이-핸드 (2인) |
| `2-NEXT STREAM STARTING SOON` | 2 | event_name, tournament_name + slots | 스트림 시작 (2인) |
| `4-NEXT STREAM STARTING SOON` | 4 | event_name, tournament_name + slots | 스트림 시작 (4인) |
| **`_Feature Table Leaderboard`** | **9** | table_name, event_name + **name, chips, rank** | **피처 테이블 리더보드 (9명)** |

#### _Feature Table Leaderboard 슬롯 구조

```json
{
    "slots": [
        {"slot_index": 1, "fields": {"name": "DANIEL NEGREANU", "chips": "1,005,113", "rank": "1"}},
        {"slot_index": 2, "fields": {"name": "PHIL HELLMUTH", "chips": "917,676", "rank": "2"}},
        // ... slot 3-9
    ],
    "single_fields": {
        "table_name": "FEATURE TABLE",
        "event_name": "WSOP SUPER CIRCUIT CYPRUS"
    }
}
```

#### 레이어 매핑 (config/mappings/CyprusDesign.yaml)

> **주의**: AEP 파일의 실제 레이어 이름을 사용해야 함

```yaml
"_Feature Table Leaderboard":
  description: "피처 테이블 리더보드 (9명 순위 표시)"
  field_mappings:
    # 실제 AEP 레이어명: "Name 1", "Chips 1", "Date 1" 패턴
    slot1_name: "Name 1"
    slot1_chips: "Chips 1"
    slot1_rank: "Date 1"
    # ... slot 2-9 동일 패턴
    table_name: "leaderboard final table"
    event_name: "WSOP SUPER CIRCUIT CYPRUS"
```

**AEP 레이어 구조**:
| GFX 필드 | AEP 레이어명 | 설명 |
|----------|-------------|------|
| `slot{N}_name` | `Name {N}` | 플레이어 이름 (N=1~9) |
| `slot{N}_chips` | `Chips {N}` | 칩 카운트 (N=1~9) |
| `slot{N}_rank` | `Date {N}` | 순위 번호 (N=1~9) |
| `table_name` | `leaderboard final table` | 테이블 제목 |
| `event_name` | `WSOP SUPER CIRCUIT CYPRUS` | 이벤트명 |

### 5.6 상태 전이 다이어그램

```
┌──────────┐     ┌──────────────┐     ┌──────────┐     ┌──────────┐
│ pending  │────▶│  preparing   │────▶│ rendering│────▶│ encoding │
└──────────┘     └──────────────┘     └──────────┘     └──────────┘
     ▲                                                       │
     │ (Crash Recovery)                                      ▼
     │                                                 ┌──────────┐
     └─────────────────────────────────────────────────│uploading │
                                                       └────┬─────┘
                                                            │
         ┌──────────┐                              ┌────────▼────────┐
         │cancelled │◀────────────────────────────│   completed     │
         └──────────┘                              └─────────────────┘
              ▲                                            ▲
              │                                            │
         ┌────┴─────┐                                      │
         │  failed  │◀─────────────────────────────────────┘
         └──────────┘                                (실패 시)
```

---

## 6. 공통 라이브러리 (lib/)

### 6.1 client.py - NexrenderClient

```python
"""
Nexrender API 클라이언트 (비동기/동기)

기존 automation_ae의 client.py 기반으로 개선:
- 재시도 로직 내장
- 커넥션 풀 관리
- 상세 로깅
"""

from typing import Any, Callable
import httpx


class NexrenderClient:
    """비동기 Nexrender API 클라이언트"""

    def __init__(
        self,
        base_url: str,
        secret: str | None = None,
        timeout: float = 30.0,
        max_retries: int = 3,
    ):
        self.base_url = base_url
        self.secret = secret
        self.timeout = timeout
        self.max_retries = max_retries

    async def health_check(self) -> bool:
        """Nexrender 서버 헬스 체크"""
        ...

    async def submit_job(self, job_data: dict[str, Any]) -> dict[str, Any]:
        """렌더링 작업 제출"""
        ...

    async def get_job(self, job_uid: str) -> dict[str, Any]:
        """작업 상태 조회"""
        ...

    async def list_jobs(self) -> list[dict[str, Any]]:
        """모든 작업 목록"""
        ...

    async def cancel_job(self, job_uid: str) -> bool:
        """작업 취소"""
        ...

    async def poll_until_complete(
        self,
        job_uid: str,
        callback: Callable[[int, str], None] | None = None,
        timeout: int = 1800,  # 30분
        poll_interval: int = 5
    ) -> dict[str, Any]:
        """작업 완료까지 폴링"""
        ...


class NexrenderSyncClient:
    """동기 Nexrender API 클라이언트 (워커용)"""

    def submit_job(self, job_data: dict[str, Any]) -> dict[str, Any]: ...
    def get_job(self, job_uid: str) -> dict[str, Any]: ...
```

### 6.2 job_builder.py - NexrenderJobBuilder

```python
"""
Nexrender Job JSON 빌더

두 가지 방식 지원:
1. GFX Data 기반 (gfx_json 방식) - 권장
2. Template 기반 (기존 automation_ae 방식) - 레거시 호환
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class JobConfig:
    """Job 빌드 설정"""
    aep_project_path: str
    composition_name: str
    output_format: str = "mp4"
    output_dir: str = ""
    output_filename: str = ""
    callback_url: str | None = None


class NexrenderJobBuilder:
    """Nexrender Job JSON 빌더"""

    def __init__(self, config: JobConfig):
        self.config = config
        self.path_converter = PathConverter()

    def build_from_gfx_data(
        self,
        gfx_data: dict[str, Any],
        job_id: str,
    ) -> dict[str, Any]:
        """gfx_data에서 Nexrender Job JSON 생성

        Args:
            gfx_data: GFX 렌더링 데이터 (slots, single_fields 포함)
            job_id: 작업 ID

        Returns:
            Nexrender Job JSON
        """
        return {
            "template": self._build_template_section(),
            "assets": self._build_assets_from_gfx(gfx_data),
            "actions": self._build_actions_section(job_id),
        }

    def build_from_template(
        self,
        template: dict[str, Any],
        data: dict[str, Any],
        job_id: int,
    ) -> dict[str, Any]:
        """Template 모델에서 Nexrender Job JSON 생성 (레거시 호환)"""
        ...

    def _build_template_section(self) -> dict[str, Any]:
        """template 섹션 생성"""
        return {
            "src": self.path_converter.to_file_url(self.config.aep_project_path),
            "composition": self.config.composition_name,
            "outputExt": self._get_output_extension(),
        }

    def _build_assets_from_gfx(self, gfx_data: dict) -> list[dict[str, Any]]:
        """gfx_data에서 assets 배열 생성"""
        assets = []

        # Slots 처리
        for slot in gfx_data.get("slots", []):
            slot_index = slot["slot_index"]
            for field_name, value in slot["fields"].items():
                layer_name = f"slot{slot_index}_{field_name}"
                assets.append({
                    "type": "data",
                    "layerName": layer_name,
                    "property": "Source Text",
                    "value": str(value),
                })

        # Single Fields 처리
        for field_name, value in gfx_data.get("single_fields", {}).items():
            assets.append({
                "type": "data",
                "layerName": field_name,
                "property": "Source Text",
                "value": str(value),
            })

        return assets

    def _build_actions_section(self, job_id: str) -> dict[str, list]:
        """actions 섹션 생성"""
        output_path = self.path_converter.to_windows_path(
            f"{self.config.output_dir}/{job_id}.{self._get_output_extension()}"
        )

        return {
            "postrender": [
                {
                    "module": "@nexrender/action-copy",
                    "input": f"result.{self._get_output_extension()}",
                    "output": output_path,
                }
            ]
        }

    def _get_output_extension(self) -> str:
        """출력 포맷에 따른 확장자"""
        format_map = {
            "mp4": "mp4",
            "mov": "mov",
            "mov_alpha": "mov",
            "png_sequence": "png",
        }
        return format_map.get(self.config.output_format, "mp4")

    def _get_output_module(self) -> str | None:
        """출력 포맷에 따른 After Effects Output Module 반환

        mov_alpha: 알파 채널 출력 (투명 배경)
        - 사용자 정의 "Alpha MOV" Output Module 템플릿 필요
        - 설정: QuickTime > Animation 코덱 > RGB+Alpha

        Returns:
            Output Module 이름 또는 None
        """
        if self.config.output_format.lower() == "mov_alpha":
            custom_module = os.getenv("NEXRENDER_OUTPUT_MODULE_ALPHA")
            return custom_module or "Alpha MOV"
        return None

    def _get_disable_layers_script(self, layer_patterns: list[str]) -> dict[str, Any] | None:
        """배경 레이어 비활성화 JSX 스크립트 생성

        mov_alpha 모드에서 투명 배경을 위해 배경 레이어를 비활성화합니다.

        Args:
            layer_patterns: 비활성화할 레이어 이름 패턴 목록
                기본값: ["background", "Background", "BG", "bg", "배경", "solid", "Solid"]

        Returns:
            Nexrender script asset (Base64 인코딩된 JSX)
        """
        ...
```

### 6.2.1 Alpha MOV 출력 설정

**목적**: 투명 배경이 필요한 자막/오버레이 렌더링

**설정 방법**:

1. **After Effects Output Module 템플릿 생성** (최초 1회):
   - AE 렌더 큐 > Output Module Settings
   - Format: QuickTime
   - Video Codec: Animation
   - Channels: RGB+Alpha
   - 템플릿 저장: "Alpha MOV"

2. **렌더링 요청 시**:
   ```json
   {
     "output_format": "mov_alpha",
     "gfx_data": {
       "disable_layers": ["background", "BG", "solid"]  // 선택적 커스텀
     }
   }
   ```

3. **자동 처리**:
   - `outputModule: "Alpha MOV"` 설정
   - 배경 레이어 비활성화 JSX 스크립트 주입
   - 출력: `pix_fmt=argb` (알파 채널 포함)

**검증 방법**:
```bash
ffprobe -show_entries stream=pix_fmt output.mov
# 결과: pix_fmt=argb (알파 채널 포함)
```

### 6.3 path_utils.py - 경로 변환 유틸리티

```python
"""
Docker ↔ Windows 경로 변환 유틸리티

문제:
- Docker 컨테이너 내부 경로: /app/templates/file.aep
- Windows 호스트 경로: C:/claude/automation_ae/templates/file.aep
- Nexrender는 Windows 경로 필요 (file:///C:/...)

해결:
- 설정 파일 기반 경로 매핑
- 양방향 변환 지원
"""

from typing import NamedTuple


class PathMapping(NamedTuple):
    """경로 매핑 규칙"""
    docker_path: str
    windows_path: str


class PathConverter:
    """Docker ↔ Windows 경로 변환기"""

    DEFAULT_MAPPINGS = [
        PathMapping("/app/templates", "C:/claude/automation_ae/templates"),
        PathMapping("/app/output", "C:/claude/automation_ae/output"),
        PathMapping("/nas/renders", "//NAS/renders"),
    ]

    def __init__(self, mappings: list[PathMapping] | None = None):
        self.mappings = mappings or self.DEFAULT_MAPPINGS

    def to_windows_path(self, docker_path: str) -> str:
        """Docker 경로 → Windows 경로"""
        for mapping in self.mappings:
            if docker_path.startswith(mapping.docker_path):
                return docker_path.replace(
                    mapping.docker_path,
                    mapping.windows_path,
                    1
                )
        return docker_path

    def to_docker_path(self, windows_path: str) -> str:
        """Windows 경로 → Docker 경로"""
        normalized = windows_path.replace("\\", "/")
        for mapping in self.mappings:
            if normalized.startswith(mapping.windows_path):
                return normalized.replace(
                    mapping.windows_path,
                    mapping.docker_path,
                    1
                )
        return windows_path

    def to_file_url(self, path: str) -> str:
        """경로를 file:// URL로 변환 (Nexrender용)"""
        windows_path = self.to_windows_path(path)
        windows_path = windows_path.replace("\\", "/")

        # Windows 드라이브 경로 (C:/)
        if len(windows_path) >= 2 and windows_path[1] == ":":
            return f"file:///{windows_path}"

        # UNC 경로 (//NAS/)
        if windows_path.startswith("//"):
            return f"file:{windows_path}"

        return f"file:///{windows_path}"
```

### 6.4 errors.py - 에러 분류 시스템

```python
"""
에러 분류 시스템

재시도 가능 여부를 자동으로 판단하여 워커 재시도 로직에 활용.
"""

from enum import Enum
from dataclasses import dataclass


class ErrorCategory(str, Enum):
    """에러 카테고리"""
    RETRYABLE = "retryable"          # 네트워크 오류, 일시적 장애
    NON_RETRYABLE = "non_retryable"  # 설정 오류, 파일 없음
    UNKNOWN = "unknown"


# 재시도 가능 에러 패턴
RETRYABLE_PATTERNS = [
    "connection", "timeout", "network", "unavailable", "temporary",
    "503", "502", "504", "ECONNREFUSED", "ETIMEDOUT", "ENOTFOUND",
]

# 재시도 불가 에러 패턴
NON_RETRYABLE_PATTERNS = [
    "not found", "404", "invalid", "permission", "unauthorized",
    "forbidden", "does not exist", "template error",
    "composition not found", "missing file",
]


class NexrenderError(Exception):
    """Nexrender 기본 에러"""

    def __init__(self, message: str, category: ErrorCategory = ErrorCategory.UNKNOWN):
        super().__init__(message)
        self.category = category


class ErrorClassifier:
    """에러 분류기"""

    @classmethod
    def classify(cls, error: Exception) -> ErrorCategory:
        """에러를 분류하여 카테고리 반환"""
        error_str = str(error).lower()

        # 패턴 매칭
        for pattern in NON_RETRYABLE_PATTERNS:
            if pattern in error_str:
                return ErrorCategory.NON_RETRYABLE

        for pattern in RETRYABLE_PATTERNS:
            if pattern in error_str:
                return ErrorCategory.RETRYABLE

        # 예외 타입 기반 분류
        if isinstance(error, (TimeoutError, ConnectionError, OSError)):
            return ErrorCategory.RETRYABLE

        if isinstance(error, (ValueError, KeyError, FileNotFoundError)):
            return ErrorCategory.NON_RETRYABLE

        return ErrorCategory.UNKNOWN

    @classmethod
    def format_message(cls, error: Exception, include_traceback: bool = False) -> str:
        """에러 메시지 포맷팅"""
        category = cls.classify(error)
        label = {
            ErrorCategory.RETRYABLE: "[재시도 가능]",
            ErrorCategory.NON_RETRYABLE: "[재시도 불가]",
            ErrorCategory.UNKNOWN: "[분류되지 않음]",
        }

        message = f"{label[category]} {type(error).__name__}: {str(error)}"

        if include_traceback:
            import traceback
            message += f"\n\n상세 정보:\n{traceback.format_exc()}"

        return message
```

---

## 7. 워커 설계 (worker/)

### 7.1 main.py - 워커 엔트리포인트

```python
"""
AE-Nexrender 워커 메인 엔트리포인트

Celery 대신 폴링 기반 비동기 워커:
- Supabase render_queue 폴링
- 적응형 폴링 주기
- 우아한 종료 처리
"""

import asyncio
import signal
import uuid
from datetime import datetime, timezone

from .config import WorkerConfig
from .job_processor import JobProcessor
from .supabase_client import SupabaseQueueClient
from .health import HealthServer


class Worker:
    """AE-Nexrender 워커"""

    def __init__(self, config: WorkerConfig):
        self.config = config
        self.worker_id = uuid.uuid4()
        self.running = False
        self.current_job_id: str | None = None

        self.supabase = SupabaseQueueClient(config)
        self.processor = JobProcessor(config, self.supabase)
        self.health_server = HealthServer(self)

    async def start(self):
        """워커 시작"""
        self.running = True

        # 시그널 핸들러 등록
        for sig in (signal.SIGINT, signal.SIGTERM):
            asyncio.get_event_loop().add_signal_handler(
                sig, lambda: asyncio.create_task(self.shutdown())
            )

        # 헬스 서버 시작
        await self.health_server.start()

        # 메인 폴링 루프
        await self._polling_loop()

    async def _polling_loop(self):
        """적응형 폴링 루프"""
        empty_poll_count = 0
        poll_interval = self.config.poll_interval_default

        while self.running:
            try:
                # 1. 대기 작업 조회 및 할당
                job = await self.supabase.claim_pending_job(self.worker_id)

                if job:
                    empty_poll_count = 0
                    poll_interval = self.config.poll_interval_busy  # 5초

                    self.current_job_id = job["id"]
                    await self.processor.process(job)
                    self.current_job_id = None
                else:
                    empty_poll_count += 1
                    if empty_poll_count > self.config.empty_poll_threshold:
                        poll_interval = self.config.poll_interval_idle  # 30초

            except Exception as e:
                logger.error(f"폴링 루프 에러: {e}")
                poll_interval = self.config.poll_interval_error  # 60초

            await asyncio.sleep(poll_interval)

    async def shutdown(self):
        """우아한 종료"""
        logger.info("워커 종료 시작...")
        self.running = False

        # 현재 작업이 있으면 상태 복원
        if self.current_job_id:
            await self.supabase.release_job(self.current_job_id)

        await self.health_server.stop()
        logger.info("워커 종료 완료")


# 엔트리포인트
def run():
    config = WorkerConfig.from_env()
    worker = Worker(config)
    asyncio.run(worker.start())


if __name__ == "__main__":
    run()
```

### 7.2 job_processor.py - 작업 처리 로직

```python
"""
렌더링 작업 처리기

5단계 프로세스:
1. Job Claim (상태: pending -> preparing)
2. Nexrender JSON 생성
3. Nexrender에 작업 제출 (상태: preparing -> rendering)
4. 진행률 폴링 (상태: rendering -> encoding -> uploading)
5. 후처리 (파일 검증, NAS 복사, 상태: completed/failed)
"""

import asyncio
from datetime import datetime, timezone

from lib.client import NexrenderClient
from lib.job_builder import NexrenderJobBuilder, JobConfig
from lib.errors import ErrorClassifier, ErrorCategory, NexrenderError
from lib.path_utils import PathConverter


class JobProcessor:
    """렌더링 작업 처리기"""

    def __init__(self, config, supabase_client):
        self.config = config
        self.supabase = supabase_client
        self.nexrender = NexrenderClient(
            base_url=config.nexrender_url,
            secret=config.nexrender_secret,
        )
        self.path_converter = PathConverter()

    async def process(self, job: dict) -> dict:
        """작업 처리 메인 로직"""
        job_id = job["id"]

        try:
            # 1. 상태 업데이트: preparing
            await self.supabase.update_job_status(
                job_id, "preparing", progress=5
            )

            # 2. Nexrender Job JSON 생성
            builder = NexrenderJobBuilder(JobConfig(
                aep_project_path=self.path_converter.to_windows_path(
                    job["aep_project_path"]
                ),
                composition_name=job["composition_name"],
                output_format=job.get("output_format", "mp4"),
                output_dir=self.config.output_dir,
                callback_url=job.get("callback_url"),
            ))

            nexrender_job_data = builder.build_from_gfx_data(
                gfx_data=job["gfx_data"],
                job_id=job_id,
            )

            # 3. Nexrender에 작업 제출
            nexrender_response = await self.nexrender.submit_job(nexrender_job_data)
            nexrender_job_uid = nexrender_response.get("uid")

            await self.supabase.update_job_status(
                job_id, "rendering",
                nexrender_job_id=nexrender_job_uid,
                progress=20
            )

            # 4. 진행률 폴링
            await self._poll_nexrender_progress(job_id, nexrender_job_uid)

            # 5. 후처리 (파일 검증, NAS 복사)
            output_path = await self._post_process(job, nexrender_job_uid)

            # 6. 완료
            await self.supabase.update_job_status(
                job_id, "completed",
                progress=100,
                output_file_path=output_path,
                completed_at=datetime.now(timezone.utc).isoformat()
            )

            return {"status": "success", "job_id": job_id, "output_path": output_path}

        except Exception as e:
            await self._handle_error(job_id, e)
            raise

    async def _poll_nexrender_progress(
        self,
        job_id: str,
        nexrender_job_uid: str
    ):
        """Nexrender 작업 상태 폴링"""
        max_timeout = self.config.render_timeout  # 30분
        poll_interval = 5  # 5초
        elapsed = 0

        while elapsed < max_timeout:
            nexrender_status = await self.nexrender.get_job(nexrender_job_uid)
            state = nexrender_status.get("state", "")
            render_progress = nexrender_status.get("renderProgress", 0)
            error = nexrender_status.get("error")

            # 상태 매핑
            status_map = {
                "queued": ("rendering", 25),
                "started": ("rendering", 30),
                "downloading": ("rendering", 35),
                "rendering": ("rendering", 40 + int(render_progress * 0.4)),
                "encoding": ("encoding", 85),
                "finished": ("uploading", 95),
            }

            if state == "error":
                raise NexrenderError(f"렌더링 실패: {error}")

            if state in status_map:
                status, progress = status_map[state]
                await self.supabase.update_job_status(
                    job_id, status,
                    progress=progress,
                    nexrender_state=state
                )

            if state == "finished":
                return

            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        raise TimeoutError("렌더링 타임아웃 (30분 초과)")

    async def _post_process(self, job: dict, nexrender_job_uid: str) -> str:
        """후처리: 파일 검증, NAS 복사"""
        # 출력 파일 경로 구성
        output_filename = job.get("output_filename") or f"{job['id']}"
        output_ext = {"mp4": "mp4", "mov": "mov", "mov_alpha": "mov"}.get(
            job.get("output_format", "mp4"), "mp4"
        )
        output_path = f"{self.config.output_dir}/{output_filename}.{output_ext}"

        # 파일 존재 확인
        # NAS 복사 (필요시)

        return output_path

    async def _handle_error(self, job_id: str, error: Exception):
        """에러 처리"""
        category = ErrorClassifier.classify(error)
        message = ErrorClassifier.format_message(error)

        job = await self.supabase.get_job(job_id)
        retry_count = job.get("retry_count", 0)
        max_retries = job.get("max_retries", 3)

        if category == ErrorCategory.RETRYABLE and retry_count < max_retries:
            # 재시도 가능 → pending으로 복원
            await self.supabase.update_job_status(
                job_id, "pending",
                retry_count=retry_count + 1,
                error_message=f"[재시도 #{retry_count + 1}] {message}",
                worker_id=None,
                lock_expires_at=None
            )
        else:
            # 재시도 불가 또는 최대 재시도 초과 → failed
            await self.supabase.update_job_status(
                job_id, "failed",
                error_message=message,
                error_category=category.value,
                completed_at=datetime.now(timezone.utc).isoformat()
            )
```

### 7.3 config.py - 워커 설정

```python
"""
워커 설정

환경변수 기반 설정 관리.
"""

from dataclasses import dataclass, field
import os


@dataclass
class WorkerConfig:
    """워커 설정"""

    # Supabase
    supabase_url: str = ""
    supabase_service_key: str = ""

    # Nexrender
    nexrender_url: str = "http://localhost:3000"
    nexrender_secret: str = ""

    # 폴링 설정
    poll_interval_default: int = 10  # 기본 폴링 주기 (초)
    poll_interval_busy: int = 5      # 작업 있을 때
    poll_interval_idle: int = 30     # 작업 없을 때
    poll_interval_error: int = 60    # 에러 발생 시
    empty_poll_threshold: int = 10   # idle로 전환할 연속 빈 폴링 횟수

    # 렌더링 설정
    render_timeout: int = 1800  # 30분
    max_retries: int = 3

    # 경로 설정
    aep_template_dir: str = "D:/templates"
    output_dir: str = "C:/claude/ae_nexrender_module/output"
    nas_output_path: str = "//NAS/renders"

    # 경로 매핑
    path_mappings: list[tuple[str, str]] = field(default_factory=lambda: [
        ("/app/templates", "C:/claude/automation_ae/templates"),
        ("/app/output", "C:/claude/automation_ae/output"),
    ])

    # 헬스 서버
    health_port: int = 8080

    @classmethod
    def from_env(cls) -> "WorkerConfig":
        """환경변수에서 설정 로드"""
        return cls(
            supabase_url=os.getenv("SUPABASE_URL", ""),
            supabase_service_key=os.getenv("SUPABASE_SERVICE_KEY", ""),
            nexrender_url=os.getenv("NEXRENDER_URL", "http://localhost:3000"),
            nexrender_secret=os.getenv("NEXRENDER_SECRET", ""),
            aep_template_dir=os.getenv("AEP_TEMPLATE_DIR", "D:/templates"),
            output_dir=os.getenv("OUTPUT_DIR", "C:/claude/ae_nexrender_module/output"),
            nas_output_path=os.getenv("NAS_OUTPUT_PATH", "//NAS/renders"),
            render_timeout=int(os.getenv("RENDER_TIMEOUT", "1800")),
            max_retries=int(os.getenv("MAX_RETRIES", "3")),
            health_port=int(os.getenv("HEALTH_PORT", "8080")),
        )
```

---

## 8. 환경 변수

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `SUPABASE_URL` | Supabase 프로젝트 URL | - |
| `SUPABASE_SERVICE_KEY` | Supabase Service Role Key | - |
| `NEXRENDER_URL` | Nexrender 서버 URL | `http://localhost:3000` |
| `NEXRENDER_SECRET` | Nexrender API Secret | - |
| `AEP_TEMPLATE_DIR` | AE 템플릿 디렉토리 | `D:/templates` |
| `OUTPUT_DIR` | 렌더링 출력 디렉토리 | `C:/claude/ae_nexrender_module/output` |
| `NAS_OUTPUT_PATH` | NAS 출력 경로 | `//NAS/renders` |
| `RENDER_TIMEOUT` | 렌더링 타임아웃 (초) | `1800` |
| `MAX_RETRIES` | 최대 재시도 횟수 | `3` |
| `HEALTH_PORT` | 헬스체크 서버 포트 | `8080` |

---

## 9. automation_ae 통합

### 9.1 마이그레이션 경로

```
Phase 1: 공통 라이브러리 추출
─────────────────────────────────────────────────────────
automation_ae                    ae_nexrender_module
├── services/nexrender/          ├── lib/
│   ├── client.py  ─────────────▶│   ├── client.py
│   └── job_builder.py ─────────▶│   └── job_builder.py
├── services/                    │
│   └── gfx_slot_builder.py ────▶│   └── gfx_slot_builder.py
└── workers/                     │
    └── render_worker.py ───────▶└── worker/
                                     └── job_processor.py

Phase 2: automation_ae에서 lib/ 의존
─────────────────────────────────────────────────────────
automation_ae
├── services/nexrender/
│   └── __init__.py
│       from ae_nexrender_module.lib import (
│           NexrenderClient,
│           NexrenderJobBuilder,
│           PathConverter,
│           ErrorClassifier,
│       )
```

### 9.2 Dashboard 연동

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Sub Dashboard → render_queue → AE-Worker                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Sub Dashboard (Next.js)                                                     │
│  ├── 자막 선택                                                               │
│  ├── gfx_data 생성                                                           │
│  └── render_queue INSERT ──────────▶  Supabase                              │
│                                        render_queue                         │
│                                            │                                 │
│                                            │ Realtime 또는 Polling          │
│                                            ▼                                 │
│                                       AE-Worker                             │
│                                        ├── Job Claim                         │
│                                        ├── Nexrender 호출                    │
│                                        └── render_queue UPDATE               │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 9.3 API 스키마

**작업 생성 (Dashboard → Supabase INSERT)**:
```json
{
    "composition_name": "_MAIN Mini Chip Count",
    "aep_project_path": "/app/templates/cyprusdesign.aep",
    "gfx_data": {
        "slots": [
            {
                "slot_index": 1,
                "fields": {
                    "name": "PHIL IVEY",
                    "chips": "250,000"
                }
            }
        ],
        "single_fields": {
            "table_id": "Table 1"
        }
    },
    "output_format": "mp4",
    "priority": 5,
    "cue_item_id": "uuid-cue-item",
    "source_system": "dashboard"
}
```

**상태 조회 응답**:
```json
{
    "id": "uuid-render-queue-id",
    "status": "rendering",
    "progress": 65,
    "nexrender_state": "rendering",
    "created_at": "2026-01-15T10:00:00Z",
    "started_at": "2026-01-15T10:00:05Z"
}
```

---

## 10. 배포 요구사항

### 10.1 Docker 이미지

```dockerfile
# docker/Dockerfile
FROM python:3.11-slim

WORKDIR /app

# 의존성 설치
COPY pyproject.toml .
RUN pip install --no-cache-dir .

# 앱 코드
COPY lib/ ./lib/
COPY worker/ ./worker/

# 환경변수
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# 헬스체크
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# 시작
CMD ["python", "-m", "worker.main"]
```

### 10.2 docker-compose.yml

```yaml
version: '3.9'

services:
  ae-worker:
    build:
      context: .
      dockerfile: docker/Dockerfile
    environment:
      - SUPABASE_URL=${SUPABASE_URL}
      - SUPABASE_SERVICE_KEY=${SUPABASE_SERVICE_KEY}
      - NEXRENDER_URL=http://host.docker.internal:3000
      - OUTPUT_DIR=/output
      - NAS_OUTPUT_PATH=//NAS/renders
    volumes:
      - ./output:/output
      - D:/templates:/templates
    ports:
      - "8080:8080"
    restart: unless-stopped
```

### 10.3 pyproject.toml

```toml
[project]
name = "ae-nexrender-module"
version = "2.0.0"
requires-python = ">=3.11"
dependencies = [
    "httpx>=0.27.0",
    "supabase>=2.0.0",
    "pydantic>=2.0.0",
    "pydantic-settings>=2.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "ruff>=0.1.0",
]

[project.scripts]
ae-worker = "worker.main:run"

[tool.ruff]
line-length = 100
target-version = "py311"
```

---

## 11. 성공 지표

### 11.1 기술 지표

| 지표 | 목표 | 측정 방법 |
|------|------|---------|
| **가용성** | 99.5% | Uptime monitoring |
| **성공률** | > 95% | (Completed) / (Total) |
| **폴링 지연** | < 10초 | 작업 생성 → Claim 시간 |
| **재시도 성공률** | > 80% | (Retried & Success) / (Retried) |
| **Crash Recovery** | < 30분 | lock_expires_at 기반 복구 |

### 11.2 비즈니스 지표

| 지표 | 목표 | 측정 방법 |
|------|------|---------|
| **렌더링 처리량** | 50+ jobs/hour | Job count |
| **평균 렌더링 시간** | < 5분 | (Completed_at - Started_at) |
| **인프라 비용** | 30% 절감 | Celery/Redis 제거 |

---

## 12. 로드맵

### Phase 1: 공통 라이브러리 (lib/)
- [ ] `lib/client.py` - NexrenderClient 포팅
- [ ] `lib/job_builder.py` - NexrenderJobBuilder 포팅
- [ ] `lib/path_utils.py` - PathConverter 신규 작성
- [ ] `lib/errors.py` - ErrorClassifier 포팅
- [ ] `lib/types.py` - 공용 타입 정의

### Phase 2: Supabase 스키마
- [ ] `migrations/001_render_queue.sql` - 테이블/인덱스
- [ ] `migrations/002_rpc_functions.sql` - claim_render_job
- [ ] RLS 정책 적용

### Phase 3: 워커 구현 (worker/)
- [ ] `worker/config.py` - 환경변수 설정
- [ ] `worker/supabase_client.py` - Supabase CRUD
- [ ] `worker/job_processor.py` - 렌더링 처리
- [ ] `worker/main.py` - 폴링 루프
- [ ] `worker/health.py` - 헬스체크

### Phase 4: 테스트 및 통합
- [ ] 단위 테스트
- [ ] automation_ae 통합 테스트
- [ ] E2E 테스트

### Phase 5: 배포
- [ ] Docker 이미지 빌드
- [ ] 스테이징 배포
- [ ] 프로덕션 배포

---

## 13. 체크리스트 (Checklist)

- [ ] PRD 리뷰 및 승인
- [ ] Supabase 스키마 설계 확정
- [ ] 공통 라이브러리 인터페이스 확정
- [ ] 개발 환경 구성
- [ ] lib/ 모듈 구현
- [ ] worker/ 모듈 구현
- [ ] 단위 테스트 작성
- [ ] 통합 테스트 작성
- [ ] Docker 이미지 빌드
- [ ] 배포 문서 작성
- [ ] 스테이징 배포
- [ ] E2E 테스트
- [ ] 프로덕션 배포
- [ ] 모니터링 설정

---

**문서 버전 관리**

| 버전 | 날짜 | 변경 사항 | 작성자 |
|------|------|---------|--------|
| 1.0 | 2026-01-15 | 초안 작성 (PostgreSQL + Celery) | Backend Team |
| 2.0 | 2026-01-15 | Supabase 기반 재설계 | Claude Code |
| 2.1 | 2026-01-16 | Alpha MOV 출력 기능 추가, 배경 레이어 비활성화 기능 | Claude Code |
| 2.2 | 2026-01-19 | `_Feature Table Leaderboard` 컴포지션 추가 (9슬롯), 기본 출력 경로를 레포 하위 폴더로 변경 (`C:/claude/ae_nexrender_module/output`), `mov_alpha` 기본값 강제화 문서화, AEP 레이어명 매핑 수정 (`SLOT1_NAME` → `Name 1`) | Claude Code |
