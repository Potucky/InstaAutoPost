-- InstaAutoPost — Prevent Duplicate Active Queue Rows
-- Migration: 20260523002000_prevent_duplicate_active_queue_rows.sql
--
-- Purpose:
--   Add a partial unique index on public.ig_publishing_queue(content_id) that
--   prevents more than one active queue row existing for the same content item
--   at the same time.
--
-- Active statuses covered by the index:
--   scheduled, ready, processing, retry_scheduled
--
-- Terminal / non-active statuses (allow future re-queue):
--   published, failed, cancelled
--
-- draft is not active and is not covered by this index.
--
-- Duplicate detection:
--   The DO block below checks for existing duplicates before attempting index
--   creation. If duplicates are found the migration fails with a clear exception.
--   Resolve duplicates manually using the diagnostic query in docs/SUPABASE_SCHEMA.md
--   before re-running this migration.
--
-- Idempotency:
--   CREATE UNIQUE INDEX IF NOT EXISTS is a no-op if the index already exists.
--   The DO block always runs; it is safe when no duplicates are present.
--
-- Application note for UI / scripts:
--   When an INSERT into ig_publishing_queue violates this index, Postgres raises
--   error code 23505 (unique_violation). Callers should treat 23505 from index
--   uidx_ig_publishing_queue_active_content_id as "content is already queued".
--   Handling 23505 in UI and worker scripts is a follow-up task.

-- ===========================================================================
-- 1. Fail-fast duplicate check
-- ===========================================================================
-- Raises an exception if any content_id already has more than one active queue
-- row. Active = scheduled, ready, processing, retry_scheduled.
-- Do not resolve duplicates automatically — operator must inspect and decide.

DO $$
DECLARE
  v_duplicate_count INTEGER;
BEGIN
  SELECT COUNT(*)
  INTO   v_duplicate_count
  FROM (
    SELECT content_id
    FROM   public.ig_publishing_queue
    WHERE  queue_status IN ('scheduled', 'ready', 'processing', 'retry_scheduled')
    GROUP  BY content_id
    HAVING COUNT(*) > 1
  ) dupes;

  IF v_duplicate_count > 0 THEN
    RAISE EXCEPTION
      'Duplicate active ig_publishing_queue rows exist. Resolve duplicates before creating the unique index.';
  END IF;
END;
$$;

-- ===========================================================================
-- 2. Partial unique index
-- ===========================================================================
-- Enforces at most one active queue row per content_id.
-- Rows with terminal or draft statuses are not covered and do not conflict.

CREATE UNIQUE INDEX IF NOT EXISTS uidx_ig_publishing_queue_active_content_id
  ON public.ig_publishing_queue (content_id)
  WHERE queue_status IN ('scheduled', 'ready', 'processing', 'retry_scheduled');

COMMENT ON INDEX uidx_ig_publishing_queue_active_content_id IS
  'Allows at most one active publishing queue row per content_id. '
  'Active statuses: scheduled, ready, processing, retry_scheduled.';
