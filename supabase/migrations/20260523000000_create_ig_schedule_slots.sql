-- InstaAutoPost Schedule Slots Layer
-- Migration: 20260523000000_create_ig_schedule_slots.sql
--
-- ig_schedule_slots is the user-facing calendar/schedule plan.
-- ig_publishing_queue remains the technical worker queue.
-- Slots start empty; content and queue rows are assigned later.

-- ---------------------------------------------------------------------------
-- Table: ig_schedule_slots
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.ig_schedule_slots (
  id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  slot_date    DATE        NOT NULL,
  slot_window  TEXT        NOT NULL CHECK (slot_window IN ('morning', 'lunch', 'evening')),
  scheduled_at TIMESTAMPTZ NOT NULL,
  content_id   UUID        REFERENCES public.ig_content_library(id) ON DELETE SET NULL,
  queue_id     UUID        REFERENCES public.ig_publishing_queue(id) ON DELETE SET NULL,
  slot_status  TEXT        NOT NULL DEFAULT 'empty'
                           CHECK (slot_status IN ('empty', 'assigned', 'queued', 'published', 'failed', 'cancelled')),
  notes        TEXT,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE public.ig_schedule_slots IS
  'User-facing calendar/schedule plan. Each row is one posting window slot. '
  'Empty slots have no content or queue assignment. The publishing worker '
  'operates on ig_publishing_queue rows, not directly on this table.';

-- ---------------------------------------------------------------------------
-- Unique constraints
-- ---------------------------------------------------------------------------

-- Each scheduled_at moment can appear only once across all slots.
ALTER TABLE public.ig_schedule_slots
  ADD CONSTRAINT ig_schedule_slots_scheduled_at_unique UNIQUE (scheduled_at);

-- A content item may be assigned to at most one slot (partial: only when set).
CREATE UNIQUE INDEX ig_schedule_slots_content_id_unique
  ON public.ig_schedule_slots (content_id)
  WHERE content_id IS NOT NULL;

-- ---------------------------------------------------------------------------
-- Indexes
-- ---------------------------------------------------------------------------
CREATE INDEX ig_schedule_slots_slot_date_idx    ON public.ig_schedule_slots (slot_date);
CREATE INDEX ig_schedule_slots_scheduled_at_idx ON public.ig_schedule_slots (scheduled_at);
CREATE INDEX ig_schedule_slots_slot_status_idx  ON public.ig_schedule_slots (slot_status);
CREATE INDEX ig_schedule_slots_content_id_idx   ON public.ig_schedule_slots (content_id);
CREATE INDEX ig_schedule_slots_queue_id_idx     ON public.ig_schedule_slots (queue_id);

-- ---------------------------------------------------------------------------
-- updated_at trigger (reuse pattern from existing tables)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.set_ig_schedule_slots_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$;

CREATE TRIGGER trg_ig_schedule_slots_updated_at
  BEFORE UPDATE ON public.ig_schedule_slots
  FOR EACH ROW EXECUTE FUNCTION public.set_ig_schedule_slots_updated_at();

-- ---------------------------------------------------------------------------
-- RLS
-- ---------------------------------------------------------------------------
ALTER TABLE public.ig_schedule_slots ENABLE ROW LEVEL SECURITY;

-- Development policy: authenticated users can read and write their own slots.
-- Tighten to per-user scoping when created_by column is added.
CREATE POLICY "authenticated users can select schedule slots"
  ON public.ig_schedule_slots FOR SELECT
  TO authenticated USING (true);

CREATE POLICY "authenticated users can insert schedule slots"
  ON public.ig_schedule_slots FOR INSERT
  TO authenticated WITH CHECK (true);

CREATE POLICY "authenticated users can update schedule slots"
  ON public.ig_schedule_slots FOR UPDATE
  TO authenticated USING (true);

-- Service role bypasses RLS by default; no explicit policy needed for worker.
