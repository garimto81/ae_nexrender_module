-- ============================================================================
-- 001_render_queue.sql
-- render_queue: Supabase 렌더링 작업 큐
-- ============================================================================

-- render_queue 테이블 생성
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

-- ============================================================================
-- render_queue_audit: 상태 변경 감사 로그 (선택)
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
