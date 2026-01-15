-- ============================================================================
-- 002_rls_policies.sql
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
