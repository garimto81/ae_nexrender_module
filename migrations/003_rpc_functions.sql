-- ============================================================================
-- 003_rpc_functions.sql
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
