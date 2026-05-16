-- InstaAutoPost Database Schema
-- Migration: 20260516000000_create_instaautopost_schema.sql

-- ---------------------------------------------------------------------------
-- Extensions
-- ---------------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ---------------------------------------------------------------------------
-- Enums
-- ---------------------------------------------------------------------------
CREATE TYPE public.content_status AS ENUM (
  'draft',
  'approved',
  'archived'
);

CREATE TYPE public.queue_status AS ENUM (
  'draft',
  'scheduled',
  'ready',
  'processing',
  'published',
  'failed',
  'cancelled',
  'retry_scheduled'
);

CREATE TYPE public.attempt_status AS ENUM (
  'success',
  'failed',
  'dry_run'
);

-- ---------------------------------------------------------------------------
-- Table 1: ig_content_library
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.ig_content_library (
  id               UUID              PRIMARY KEY DEFAULT uuid_generate_v4(),
  title            TEXT              NOT NULL,
  caption          TEXT,
  video_url        TEXT              NOT NULL,
  thumbnail_url    TEXT,
  hashtags         TEXT[],
  content_status   public.content_status NOT NULL DEFAULT 'draft',
  media_type       TEXT              NOT NULL DEFAULT 'video',
  duration_seconds INTEGER,
  file_size        BIGINT,
  created_by       UUID              REFERENCES auth.users(id) ON DELETE SET NULL,
  created_at       TIMESTAMPTZ       NOT NULL DEFAULT NOW(),
  updated_at       TIMESTAMPTZ       NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE public.ig_content_library IS
  'Master library of all video content assets. Never deleted — archived instead.';

-- ---------------------------------------------------------------------------
-- Table 2: ig_publishing_queue
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.ig_publishing_queue (
  id                UUID              PRIMARY KEY DEFAULT uuid_generate_v4(),
  content_id        UUID              NOT NULL REFERENCES public.ig_content_library(id) ON DELETE CASCADE,
  queue_status      public.queue_status NOT NULL DEFAULT 'draft',
  scheduled_at      TIMESTAMPTZ       NOT NULL DEFAULT NOW(),
  published_at      TIMESTAMPTZ,
  external_media_id TEXT,
  attempt_count     INTEGER           NOT NULL DEFAULT 0,
  max_attempts      INTEGER           NOT NULL DEFAULT 3,
  next_retry_at     TIMESTAMPTZ,
  error_message     TEXT,
  ig_user_id        TEXT,
  notes             TEXT,
  locked_at         TIMESTAMPTZ,
  locked_by         TEXT,
  created_by        UUID              REFERENCES auth.users(id) ON DELETE SET NULL,
  created_at        TIMESTAMPTZ       NOT NULL DEFAULT NOW(),
  updated_at        TIMESTAMPTZ       NOT NULL DEFAULT NOW(),

  -- Completion proof: both must be set together, or neither
  CONSTRAINT chk_published_proof CHECK (
    (published_at IS NULL AND external_media_id IS NULL)
    OR (published_at IS NOT NULL AND external_media_id IS NOT NULL)
  )
);

COMMENT ON TABLE public.ig_publishing_queue IS
  'Scheduling ledger. queue_status is the control field. published_at + external_media_id is completion proof.';

COMMENT ON COLUMN public.ig_publishing_queue.scheduled_at IS
  'Trigger: worker selects items where scheduled_at <= NOW() and queue_status is actionable.';

COMMENT ON COLUMN public.ig_publishing_queue.locked_at IS
  'Worker lock timestamp. Locks older than 10 minutes are reclaimed automatically.';

-- ---------------------------------------------------------------------------
-- Table 3: ig_publish_attempts
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.ig_publish_attempts (
  id              UUID              PRIMARY KEY DEFAULT uuid_generate_v4(),
  queue_id        UUID              NOT NULL REFERENCES public.ig_publishing_queue(id) ON DELETE CASCADE,
  attempted_at    TIMESTAMPTZ       NOT NULL DEFAULT NOW(),
  attempt_number  INTEGER           NOT NULL DEFAULT 1,
  status          public.attempt_status NOT NULL,
  response_data   JSONB,
  error_message   TEXT,
  container_id    TEXT,
  media_id        TEXT,
  duration_ms     INTEGER,
  dry_run         BOOLEAN           NOT NULL DEFAULT FALSE,
  worker_version  TEXT,
  created_at      TIMESTAMPTZ       NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE public.ig_publish_attempts IS
  'Audit log of every publish attempt including dry runs.';

-- ---------------------------------------------------------------------------
-- Indexes
-- ---------------------------------------------------------------------------
CREATE INDEX idx_ig_content_library_status
  ON public.ig_content_library(content_status);

CREATE INDEX idx_ig_content_library_created_at
  ON public.ig_content_library(created_at DESC);

CREATE INDEX idx_ig_publishing_queue_status
  ON public.ig_publishing_queue(queue_status);

CREATE INDEX idx_ig_publishing_queue_scheduled_at
  ON public.ig_publishing_queue(scheduled_at);

CREATE INDEX idx_ig_publishing_queue_content_id
  ON public.ig_publishing_queue(content_id);

-- Composite index for the worker's due-item query
CREATE INDEX idx_ig_publishing_queue_due ON public.ig_publishing_queue(
  queue_status,
  scheduled_at,
  published_at,
  external_media_id,
  attempt_count,
  next_retry_at
);

CREATE INDEX idx_ig_publish_attempts_queue_id
  ON public.ig_publish_attempts(queue_id);

CREATE INDEX idx_ig_publish_attempts_status
  ON public.ig_publish_attempts(status);

CREATE INDEX idx_ig_publish_attempts_attempted_at
  ON public.ig_publish_attempts(attempted_at DESC);

-- ---------------------------------------------------------------------------
-- updated_at trigger
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$;

CREATE TRIGGER trg_ig_content_library_updated_at
  BEFORE UPDATE ON public.ig_content_library
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_ig_publishing_queue_updated_at
  BEFORE UPDATE ON public.ig_publishing_queue
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- ---------------------------------------------------------------------------
-- Atomic row-claim function (used by publisher worker)
-- ---------------------------------------------------------------------------
-- Worker-only RPC. SECURITY DEFINER runs as the function owner (postgres/admin),
-- so search_path must be pinned to prevent schema-injection attacks.
-- Execute is explicitly restricted to service_role; anon/authenticated are denied.
CREATE OR REPLACE FUNCTION public.claim_next_queue_item(p_worker_id TEXT)
RETURNS SETOF public.ig_publishing_queue
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_catalog
AS $$
DECLARE
  v_item_id UUID;
BEGIN
  -- Select one due item and lock it; skip any already locked by another worker
  SELECT id INTO v_item_id
  FROM public.ig_publishing_queue
  WHERE queue_status IN ('ready', 'scheduled', 'retry_scheduled')
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
    RETURN; -- Nothing due right now
  END IF;

  -- Atomically mark as processing and increment attempt_count
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
  'Worker-only. Atomically selects and locks one due queue item for the publisher worker. Uses FOR UPDATE SKIP LOCKED to prevent concurrent duplicate processing. Execute is restricted to service_role; public execute is revoked.';

-- Harden RPC execution boundary.
-- PostgreSQL grants EXECUTE to PUBLIC by default; revoke it explicitly so that
-- anon and authenticated JWT roles cannot invoke this function directly.
-- Only the backend service worker (running as service_role) may call it.
REVOKE EXECUTE ON FUNCTION public.claim_next_queue_item(TEXT) FROM PUBLIC;
GRANT  EXECUTE ON FUNCTION public.claim_next_queue_item(TEXT) TO   service_role;

-- Defense-in-depth: explicit per-role revokes in case a future migration
-- accidentally re-grants EXECUTE to a specific role.
-- REVOKE FROM PUBLIC above already covers both, but naming them explicitly
-- ensures the intent is unambiguous.
REVOKE EXECUTE ON FUNCTION public.claim_next_queue_item(TEXT) FROM anon;
REVOKE EXECUTE ON FUNCTION public.claim_next_queue_item(TEXT) FROM authenticated;

-- ---------------------------------------------------------------------------
-- Row Level Security
-- ---------------------------------------------------------------------------
ALTER TABLE public.ig_content_library    ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ig_publishing_queue   ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ig_publish_attempts   ENABLE ROW LEVEL SECURITY;
