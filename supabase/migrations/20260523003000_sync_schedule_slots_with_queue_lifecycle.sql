-- InstaAutoPost — Sync Schedule Slots with Queue Lifecycle (Phase 1)
-- Migration: 20260523003000_sync_schedule_slots_with_queue_lifecycle.sql
--
-- Purpose:
--   Add DB-level synchronization so that when an ig_publishing_queue row
--   changes lifecycle state, the linked ig_schedule_slots row is automatically
--   updated to project that state.
--
-- Architecture contract:
--   ig_publishing_queue is the lifecycle source of truth.
--   ig_schedule_slots is a calendar projection — it reflects queue state but
--   does not drive it. The publishing worker reads and writes only the queue.
--
-- What this migration does:
--   1. Preflight integrity checks (abort if pre-existing violations exist).
--   2. Drop the global content_id uniqueness index; replace with a narrower
--      active-slot partial index (assigned, queued only).
--   3. Add a partial unique index on queue_id (IS NOT NULL).
--   4. Add helper function derive_slot_status_from_queue().
--   5. Add trigger function sync_slot_with_queue_lifecycle().
--   6. Add AFTER INSERT OR UPDATE trigger on ig_publishing_queue.
--
-- What is NOT done here (Phase 2 / follow-up app task):
--   Creating ig_schedule_slots rows from queue rows, or creating queue rows
--   from assigned slot rows, is an application-level operation. That operation
--   must link the rows atomically (set slot.queue_id = queue.id) so the trigger
--   can maintain the projection going forward.
--
-- failed / cancelled behavior:
--   When a queue row reaches failed or cancelled status, the linked slot is
--   marked failed or cancelled. It is NOT automatically released back to
--   'assigned' or 'empty'. An operator or future app task must explicitly
--   re-assign content if a retry is desired.
--
-- Published proof:
--   published_at and external_media_id remain on ig_publishing_queue.
--   ig_schedule_slots.slot_status = 'published' is a projection only.
--
-- slot_date timezone:
--   Derived as (scheduled_at AT TIME ZONE 'America/New_York')::date so the
--   calendar date reflects the local posting day rather than UTC midnight.
--
-- Idempotency:
--   CREATE OR REPLACE FUNCTION, DROP TRIGGER IF EXISTS + CREATE TRIGGER,
--   and DROP INDEX IF EXISTS + CREATE UNIQUE INDEX IF NOT EXISTS are used
--   throughout. Safe to re-run on a clean database.

-- ===========================================================================
-- 1. Preflight integrity checks
-- ===========================================================================
-- All three checks run in a single DO block. Any failure aborts the migration
-- before any schema objects are modified.

DO $$
DECLARE
  v_count INTEGER;
BEGIN

  -- Check 1: duplicate non-null queue_id values in ig_schedule_slots.
  -- Each non-null queue_id must map to exactly one slot before the partial
  -- unique index can be created safely.
  SELECT COUNT(*) INTO v_count
  FROM (
    SELECT queue_id
    FROM   public.ig_schedule_slots
    WHERE  queue_id IS NOT NULL
    GROUP  BY queue_id
    HAVING COUNT(*) > 1
  ) dupes;

  IF v_count > 0 THEN
    RAISE EXCEPTION
      'Duplicate queue_id values found in ig_schedule_slots. '
      'Each non-null queue_id must appear in at most one slot row. '
      'Resolve duplicates before running this migration.';
  END IF;

  -- Check 2: linked slots whose content_id differs from their queue row content_id.
  -- The trigger will overwrite slot.content_id with queue.content_id on every
  -- update, so pre-existing mismatches must be resolved first.
  SELECT COUNT(*) INTO v_count
  FROM   public.ig_schedule_slots  s
  JOIN   public.ig_publishing_queue q ON q.id = s.queue_id
  WHERE  s.queue_id    IS NOT NULL
    AND  s.content_id  IS DISTINCT FROM q.content_id;

  IF v_count > 0 THEN
    RAISE EXCEPTION
      'Linked ig_schedule_slots rows found where content_id does not match '
      'the linked ig_publishing_queue content_id. '
      'Resolve content_id mismatches before running this migration.';
  END IF;

  -- Check 3: duplicate active-slot content_id values.
  -- The replacement partial unique index covers slot_status IN (assigned, queued).
  -- Existing duplicates under those statuses must be resolved before the index
  -- can be created.
  SELECT COUNT(*) INTO v_count
  FROM (
    SELECT content_id
    FROM   public.ig_schedule_slots
    WHERE  slot_status IN ('assigned', 'queued')
      AND  content_id IS NOT NULL
    GROUP  BY content_id
    HAVING COUNT(*) > 1
  ) dupes;

  IF v_count > 0 THEN
    RAISE EXCEPTION
      'Duplicate content_id values found in ig_schedule_slots with active '
      'slot_status (assigned or queued). '
      'Resolve duplicates before running this migration.';
  END IF;

END;
$$;

-- ===========================================================================
-- 2. Replace global content_id index with active-slot partial index
-- ===========================================================================
-- The original index ig_schedule_slots_content_id_unique enforced uniqueness
-- for ALL non-null content_id values regardless of slot_status. This blocked
-- creating a new slot for the same content after an old slot reached a terminal
-- status (published, failed, cancelled).
--
-- Replacement: cover only active statuses (assigned, queued) so that content
-- can be re-scheduled after a slot exits the active lifecycle.

DROP INDEX IF EXISTS ig_schedule_slots_content_id_unique;
DROP INDEX IF EXISTS uidx_ig_schedule_slots_active_content_id;

CREATE UNIQUE INDEX IF NOT EXISTS uidx_ig_schedule_slots_active_content_id
  ON public.ig_schedule_slots (content_id)
  WHERE content_id IS NOT NULL
    AND slot_status IN ('assigned', 'queued');

COMMENT ON INDEX uidx_ig_schedule_slots_active_content_id IS
  'At most one active slot per content_id. '
  'Active slot statuses: assigned, queued. '
  'Terminal statuses (published, failed, cancelled) and empty do not conflict, '
  'allowing re-scheduling of the same content after a slot exits the active lifecycle.';

-- ===========================================================================
-- 3. Partial unique index on queue_id
-- ===========================================================================
-- Prevents a single ig_publishing_queue row from being linked to more than
-- one slot. NULL queue_id is permitted (slot not yet linked to a queue row).

DROP INDEX IF EXISTS uidx_ig_schedule_slots_queue_id;

CREATE UNIQUE INDEX IF NOT EXISTS uidx_ig_schedule_slots_queue_id
  ON public.ig_schedule_slots (queue_id)
  WHERE queue_id IS NOT NULL;

COMMENT ON INDEX uidx_ig_schedule_slots_queue_id IS
  'Each non-null queue_id may appear in at most one ig_schedule_slots row. '
  'Prevents a queue row from being linked to multiple calendar slots.';

-- ===========================================================================
-- 4. Helper function: derive slot_status from queue lifecycle state
-- ===========================================================================
-- Maps the relevant fields of an ig_publishing_queue row to the correct
-- ig_schedule_slots.slot_status value.
--
-- Derivation rules (evaluated in order):
--   published_at IS NOT NULL OR external_media_id IS NOT NULL → 'published'
--   queue_status = 'failed'    → 'failed'
--   queue_status = 'cancelled' → 'cancelled'
--   all other queue statuses   → 'queued'
--
-- IMMUTABLE: result depends only on the three input values. Safe to use
-- inside the trigger and in ad-hoc queries.

CREATE OR REPLACE FUNCTION public.derive_slot_status_from_queue(
  p_published_at      TIMESTAMPTZ,
  p_external_media_id TEXT,
  p_queue_status      TEXT
)
RETURNS TEXT
LANGUAGE sql
IMMUTABLE
AS $$
  SELECT CASE
    WHEN p_published_at IS NOT NULL OR p_external_media_id IS NOT NULL THEN 'published'
    WHEN p_queue_status = 'failed'    THEN 'failed'
    WHEN p_queue_status = 'cancelled' THEN 'cancelled'
    ELSE 'queued'
  END;
$$;

COMMENT ON FUNCTION public.derive_slot_status_from_queue IS
  'Maps ig_publishing_queue lifecycle state to ig_schedule_slots.slot_status. '
  'Published proof (published_at or external_media_id) takes precedence. '
  'failed and cancelled propagate directly. All other statuses map to queued.';

-- ===========================================================================
-- 5. Trigger function: sync linked slot when queue row changes
-- ===========================================================================
-- Fires AFTER INSERT OR UPDATE on ig_publishing_queue.
-- Updates the ig_schedule_slots row linked via queue_id = NEW.id.
--
-- Columns updated on the slot:
--   content_id   — kept in sync with the queue row (FK anchor).
--   scheduled_at — kept in sync so calendar and worker agree on publish time.
--   slot_date    — re-derived from scheduled_at in America/New_York timezone.
--   slot_status  — derived from queue lifecycle via derive_slot_status_from_queue().
--   updated_at   — refreshed to now().
--
-- Columns intentionally NOT updated:
--   slot_window  — the user's scheduling window choice; not derived from the queue.
--   notes        — free-text annotation; not derived from the queue.
--   id, created_at — immutable.
--
-- On INSERT of a new queue row with no linked slot, the UPDATE affects zero rows.
-- This is expected — the app links a slot to a queue row by setting
-- slot.queue_id = queue.id in the same transaction that creates the queue row.
-- Once linked, all subsequent queue updates propagate automatically.
--
-- Service role (worker / GitHub Actions) bypasses RLS. The trigger fires in the
-- context of the caller, so worker queue updates propagate to slots without
-- requiring explicit RLS grants on ig_schedule_slots.

CREATE OR REPLACE FUNCTION public.sync_slot_with_queue_lifecycle()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
  -- ig_publishing_queue is the lifecycle source of truth.
  -- ig_schedule_slots is a calendar projection — update it to reflect queue state.
  -- slot_window is intentionally excluded: it is the user's scheduling choice,
  -- not a value derived from the queue row.
  UPDATE public.ig_schedule_slots
  SET
    content_id   = NEW.content_id,
    scheduled_at = NEW.scheduled_at,
    slot_date    = (NEW.scheduled_at AT TIME ZONE 'America/New_York')::date,
    slot_status  = public.derive_slot_status_from_queue(
                     NEW.published_at,
                     NEW.external_media_id,
                     NEW.queue_status::text
                   ),
    updated_at   = now()
  WHERE queue_id = NEW.id;

  RETURN NULL;
END;
$$;

COMMENT ON FUNCTION public.sync_slot_with_queue_lifecycle IS
  'AFTER INSERT OR UPDATE trigger function on ig_publishing_queue. '
  'Updates the linked ig_schedule_slots row (if any) to project queue lifecycle '
  'state. Does not create or delete slot rows. Does not modify slot_window.';

-- ===========================================================================
-- 6. Trigger on ig_publishing_queue
-- ===========================================================================

DROP TRIGGER IF EXISTS trg_sync_slot_with_queue_lifecycle
  ON public.ig_publishing_queue;

CREATE TRIGGER trg_sync_slot_with_queue_lifecycle
  AFTER INSERT OR UPDATE ON public.ig_publishing_queue
  FOR EACH ROW EXECUTE FUNCTION public.sync_slot_with_queue_lifecycle();

COMMENT ON TRIGGER trg_sync_slot_with_queue_lifecycle
  ON public.ig_publishing_queue IS
  'Propagates queue lifecycle changes to the linked ig_schedule_slots row. '
  'Fires on every INSERT or UPDATE of a queue row. '
  'ig_publishing_queue remains the source of truth; '
  'ig_schedule_slots is a read-only calendar projection for the UI.';
