-- InstaAutoPost — Fix queue schema drift and stale processing recovery
-- Migration: 20260516002000_fix_queue_schema_and_stale_processing.sql
--
-- Purpose:
--   1. Add failure_reason and worker_metadata columns to ig_publishing_queue
--      (live DB already has them; IF NOT EXISTS makes this idempotent).
--   2. Drop the incorrect error_message column from ig_publishing_queue.
--      Queue-level failure state belongs in failure_reason only.
--      error_message remains valid on ig_publish_attempts.
--   3. Update claim_next_queue_item to also reclaim stale processing rows
--      (locked_at older than 10 minutes) so stuck rows are not permanent.
--
-- WARNING before applying to live:
--   If ig_publishing_queue.error_message contains live data, migrate it to
--   failure_reason before running the DROP COLUMN statement below.

-- ---------------------------------------------------------------------------
-- Step 1: Add missing columns (idempotent — safe if already present in live DB)
-- ---------------------------------------------------------------------------
ALTER TABLE public.ig_publishing_queue
  ADD COLUMN IF NOT EXISTS failure_reason TEXT;

ALTER TABLE public.ig_publishing_queue
  ADD COLUMN IF NOT EXISTS worker_metadata JSONB;

COMMENT ON COLUMN public.ig_publishing_queue.failure_reason IS
  'Last queue-level failure reason. Set by the worker; cleared on success.';

COMMENT ON COLUMN public.ig_publishing_queue.worker_metadata IS
  'Worker-owned JSONB for diagnostics and manual reconciliation state.';

-- ---------------------------------------------------------------------------
-- Step 2: Drop the incorrect error_message column from ig_publishing_queue.
-- Queue failure state belongs in failure_reason (above).
-- error_message is valid only on ig_publish_attempts.
-- ---------------------------------------------------------------------------
ALTER TABLE public.ig_publishing_queue
  DROP COLUMN IF EXISTS error_message;

-- ---------------------------------------------------------------------------
-- Step 3: Update claim_next_queue_item to reclaim stale processing rows.
--
-- The original function only selected rows with queue_status IN
-- ('ready', 'scheduled', 'retry_scheduled'). A row stuck in 'processing'
-- with an expired lock was never reclaimed, becoming permanently stuck.
--
-- Fix: include 'processing' in the eligible status list. The existing
-- locked_at condition (locked_at < NOW() - INTERVAL '10 minutes') ensures
-- only genuinely abandoned rows are reclaimed — an actively processing row
-- with a fresh lock is skipped via FOR UPDATE SKIP LOCKED.
--
-- attempt_count is incremented on reclaim (a new real attempt is starting).
-- Rows at max_attempts cannot be reclaimed; an operator must resolve them.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.claim_next_queue_item(p_worker_id TEXT)
RETURNS SETOF public.ig_publishing_queue
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_catalog
AS $$
DECLARE
  v_item_id UUID;
BEGIN
  SELECT id INTO v_item_id
  FROM public.ig_publishing_queue
  WHERE queue_status IN ('ready', 'scheduled', 'retry_scheduled', 'processing')
    AND scheduled_at <= NOW()
    AND published_at IS NULL
    AND external_media_id IS NULL
    AND attempt_count < max_attempts
    AND (next_retry_at IS NULL OR next_retry_at <= NOW())
    AND (locked_at IS NULL OR locked_at < NOW() - INTERVAL '10 minutes')
  ORDER BY scheduled_at ASC
  LIMIT 1
  FOR UPDATE SKIP LOCKED;

  IF v_item_id IS NULL THEN
    RETURN;
  END IF;

  UPDATE public.ig_publishing_queue
  SET
    queue_status  = 'processing',
    locked_at     = NOW(),
    locked_by     = p_worker_id,
    attempt_count = attempt_count + 1,
    updated_at    = NOW()
  WHERE id = v_item_id;

  RETURN QUERY SELECT * FROM public.ig_publishing_queue WHERE id = v_item_id;
END;
$$;

COMMENT ON FUNCTION public.claim_next_queue_item IS
  'Worker-only. Atomically selects and locks one due queue item. Reclaims stale processing rows (lock > 10 min). Rows at max_attempts require manual operator intervention. Execute is restricted to service_role.';

-- Re-apply execution boundary (CREATE OR REPLACE resets grants to defaults).
REVOKE EXECUTE ON FUNCTION public.claim_next_queue_item(TEXT) FROM PUBLIC;
GRANT  EXECUTE ON FUNCTION public.claim_next_queue_item(TEXT) TO   service_role;
REVOKE EXECUTE ON FUNCTION public.claim_next_queue_item(TEXT) FROM anon;
REVOKE EXECUTE ON FUNCTION public.claim_next_queue_item(TEXT) FROM authenticated;
