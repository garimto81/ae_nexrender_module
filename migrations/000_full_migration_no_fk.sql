-- ============================================================================
-- ae_nexrender_module 전체 마이그레이션 (FK 제약 없음)
--
-- Supabase SQL Editor에서 실행하세요.
-- aep_compositions 테이블이 없어도 동작합니다.
-- ============================================================================

-- ============================================================================
-- 1. render_queue 테이블 생성
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.render_queue (
    -- 기본 식별자
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- 작업 구성 (FK 제거)
    composition_id UUID,  -- aep_compositions 참조 없음
    composition_name TEXT NOT NULL,
    aep_project_path TEXT NOT NULL,

    -- 렌더링 데이터 (gfx_data JSON)
    gfx_data JSONB NOT NULL,

    -- 출력 설정
    output_format TEXT DEFAULT 'mp4' CHECK (output_format IN ('mp4', 'mov', 'png_sequence')),
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
CREATE INDEX IF NOT EXISTS idx_render_queue_status ON public.render_queue(status);
CREATE INDEX IF NOT EXISTS idx_render_queue_worker ON public.render_queue(worker_id);
CREATE INDEX IF NOT EXISTS idx_render_queue_created ON public.render_queue(created_at);
CREATE INDEX IF NOT EXISTS idx_render_queue_priority_status ON public.render_queue(priority DESC, status, created_at ASC);

-- Updated At 트리거
CREATE OR REPLACE FUNCTION update_render_queue_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_render_queue_updated_at ON public.render_queue;
CREATE TRIGGER trigger_render_queue_updated_at
BEFORE UPDATE ON public.render_queue
FOR EACH ROW
EXECUTE FUNCTION update_render_queue_updated_at();

-- ============================================================================
-- 2. render_queue_audit 테이블 (선택)
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

CREATE INDEX IF NOT EXISTS idx_render_queue_audit_queue ON public.render_queue_audit(render_queue_id);

-- ============================================================================
-- 3. RLS 정책
-- ============================================================================

-- RLS 활성화
ALTER TABLE public.render_queue ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.render_queue_audit ENABLE ROW LEVEL SECURITY;

-- 서비스 역할 (모든 권한)
DROP POLICY IF EXISTS "service_role_all" ON public.render_queue;
CREATE POLICY "service_role_all" ON public.render_queue
    FOR ALL USING (auth.jwt()->>'role' = 'service_role');

-- 워커 (자신의 작업만)
DROP POLICY IF EXISTS "worker_select_pending" ON public.render_queue;
CREATE POLICY "worker_select_pending" ON public.render_queue
    FOR SELECT USING (
        status = 'pending' OR worker_id = (auth.jwt()->>'worker_id')::UUID
    );

DROP POLICY IF EXISTS "worker_update_own" ON public.render_queue;
CREATE POLICY "worker_update_own" ON public.render_queue
    FOR UPDATE USING (
        worker_id = (auth.jwt()->>'worker_id')::UUID
    );

-- 대시보드 (읽기 + INSERT)
DROP POLICY IF EXISTS "dashboard_read" ON public.render_queue;
CREATE POLICY "dashboard_read" ON public.render_queue
    FOR SELECT USING (auth.jwt()->>'role' = 'authenticated');

DROP POLICY IF EXISTS "dashboard_insert" ON public.render_queue;
CREATE POLICY "dashboard_insert" ON public.render_queue
    FOR INSERT WITH CHECK (auth.jwt()->>'role' = 'authenticated');

-- ============================================================================
-- 4. claim_render_job RPC 함수
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

-- ============================================================================
-- 완료! 이제 render_queue 테이블을 사용할 수 있습니다.
-- ============================================================================
