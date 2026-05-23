-- InstaAutoPost — Admin-Only RLS Hardening
-- Migration: 20260523001000_harden_admin_only_rls.sql
--
-- Purpose:
--   Move InstaAutoPost from development-wide authenticated RLS policies to a
--   safer single-owner/admin-only production posture.
--
--   All browser access to core tables is restricted to users in the
--   public.instaautopost_admins allowlist. Public signup remains disabled in
--   the UI (Task 4.1). This migration does not need to enforce signup gating —
--   the allowlist check is the production safety net regardless of how a session
--   was created.
--
-- Service role / worker note:
--   The Python publisher worker (instaautopost_publisher.py) and GitHub Actions
--   use the SUPABASE_SERVICE_ROLE_KEY. Service role bypasses RLS entirely in
--   PostgreSQL/Supabase and is NOT subject to any policy in this migration.
--   claim_next_queue_item() also runs as SECURITY DEFINER (function owner), so
--   it is likewise unaffected. Worker behavior is fully preserved.
--
-- How to add the first admin user after applying this migration:
--   Run the following SQL in the Supabase SQL editor or psql:
--
--     INSERT INTO public.instaautopost_admins (user_id) VALUES ('YOUR_AUTH_USER_UUID');
--
--   YOUR_AUTH_USER_UUID is the UUID shown in Supabase dashboard under
--   Authentication > Users. Do NOT hardcode a real UUID in this file.
--
-- Idempotency:
--   DROP POLICY IF EXISTS before each CREATE POLICY makes this safe to re-run.
--   CREATE TABLE IF NOT EXISTS and CREATE OR REPLACE FUNCTION are also safe.

-- ===========================================================================
-- 1. Admin allowlist table
-- ===========================================================================

CREATE TABLE IF NOT EXISTS public.instaautopost_admins (
  user_id    UUID        PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE public.instaautopost_admins IS
  'Single-owner/admin allowlist for InstaAutoPost. A row here grants a browser '
  'session full admin access to all InstaAutoPost tables. Rows must be inserted '
  'manually via SQL — no signup flow populates this table. '
  'Service role bypasses RLS and is unaffected by this table.';

ALTER TABLE public.instaautopost_admins ENABLE ROW LEVEL SECURITY;

-- ===========================================================================
-- 2. Admin helper function
-- ===========================================================================

CREATE OR REPLACE FUNCTION public.is_instaautopost_admin()
RETURNS BOOLEAN
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT EXISTS (
    SELECT 1
    FROM public.instaautopost_admins
    WHERE user_id = auth.uid()
  );
$$;

COMMENT ON FUNCTION public.is_instaautopost_admin IS
  'Returns true when the currently authenticated browser session belongs to a '
  'user in public.instaautopost_admins. SECURITY DEFINER so that RLS on the '
  'admins table itself does not block the lookup. Used as the USING / WITH CHECK '
  'expression in every admin-only RLS policy below.';

-- ===========================================================================
-- 3. Admin table policies
--
--    Admins can read the allowlist (e.g. to confirm their own access).
--    INSERT / UPDATE / DELETE into this table must be done via SQL only —
--    no browser policy is created for write operations.
-- ===========================================================================

DROP POLICY IF EXISTS "admin_select_admins" ON public.instaautopost_admins;
CREATE POLICY "admin_select_admins"
  ON public.instaautopost_admins
  FOR SELECT
  TO authenticated
  USING (public.is_instaautopost_admin());

-- ===========================================================================
-- 4a. ig_content_library — admin-only hardening
--
-- Service role bypasses RLS; worker reads content library via service role.
-- ===========================================================================

ALTER TABLE public.ig_content_library ENABLE ROW LEVEL SECURITY;

-- Remove dev-wide authenticated policies
DROP POLICY IF EXISTS "dev_select_content" ON public.ig_content_library;
DROP POLICY IF EXISTS "dev_insert_content" ON public.ig_content_library;
DROP POLICY IF EXISTS "dev_update_content" ON public.ig_content_library;
DROP POLICY IF EXISTS "dev_delete_content" ON public.ig_content_library;

-- Remove any previous run of this migration's own policies (idempotency)
DROP POLICY IF EXISTS "admin_select_content" ON public.ig_content_library;
DROP POLICY IF EXISTS "admin_insert_content" ON public.ig_content_library;
DROP POLICY IF EXISTS "admin_update_content" ON public.ig_content_library;
DROP POLICY IF EXISTS "admin_delete_content" ON public.ig_content_library;

CREATE POLICY "admin_select_content"
  ON public.ig_content_library
  FOR SELECT
  TO authenticated
  USING (public.is_instaautopost_admin());

CREATE POLICY "admin_insert_content"
  ON public.ig_content_library
  FOR INSERT
  TO authenticated
  WITH CHECK (public.is_instaautopost_admin());

CREATE POLICY "admin_update_content"
  ON public.ig_content_library
  FOR UPDATE
  TO authenticated
  USING  (public.is_instaautopost_admin())
  WITH CHECK (public.is_instaautopost_admin());

-- Delete policy carried forward: dev_delete_content existed, so a production
-- admin delete policy is appropriate. Archive-first (content_status = 'archived')
-- remains the preferred pattern; hard delete is available to admins as a last resort.
CREATE POLICY "admin_delete_content"
  ON public.ig_content_library
  FOR DELETE
  TO authenticated
  USING (public.is_instaautopost_admin());

-- ===========================================================================
-- 4b. ig_publishing_queue — admin-only hardening
--
-- Service role bypasses RLS. claim_next_queue_item() is SECURITY DEFINER and
-- runs as the function owner (postgres/admin role), not as the authenticated
-- role — worker queue claims are unaffected by these policies.
-- ===========================================================================

ALTER TABLE public.ig_publishing_queue ENABLE ROW LEVEL SECURITY;

-- Remove dev-wide authenticated policies
DROP POLICY IF EXISTS "dev_select_queue" ON public.ig_publishing_queue;
DROP POLICY IF EXISTS "dev_insert_queue" ON public.ig_publishing_queue;
DROP POLICY IF EXISTS "dev_update_queue" ON public.ig_publishing_queue;
DROP POLICY IF EXISTS "dev_delete_queue" ON public.ig_publishing_queue;

-- Remove any previous run of this migration's own policies (idempotency)
DROP POLICY IF EXISTS "admin_select_queue" ON public.ig_publishing_queue;
DROP POLICY IF EXISTS "admin_insert_queue" ON public.ig_publishing_queue;
DROP POLICY IF EXISTS "admin_update_queue" ON public.ig_publishing_queue;
DROP POLICY IF EXISTS "admin_delete_queue" ON public.ig_publishing_queue;

CREATE POLICY "admin_select_queue"
  ON public.ig_publishing_queue
  FOR SELECT
  TO authenticated
  USING (public.is_instaautopost_admin());

CREATE POLICY "admin_insert_queue"
  ON public.ig_publishing_queue
  FOR INSERT
  TO authenticated
  WITH CHECK (public.is_instaautopost_admin());

CREATE POLICY "admin_update_queue"
  ON public.ig_publishing_queue
  FOR UPDATE
  TO authenticated
  USING  (public.is_instaautopost_admin())
  WITH CHECK (public.is_instaautopost_admin());

-- Delete policy carried forward: dev_delete_queue existed with status guards.
-- Prefer queue_status = 'cancelled' over hard-delete to preserve ig_publish_attempts
-- audit history (ON DELETE CASCADE would remove attempt rows on hard delete).
CREATE POLICY "admin_delete_queue"
  ON public.ig_publishing_queue
  FOR DELETE
  TO authenticated
  USING (
    public.is_instaautopost_admin()
    AND queue_status NOT IN ('processing', 'retry_scheduled', 'published')
  );

-- ===========================================================================
-- 4c. ig_publish_attempts — admin read-only
--
-- Attempts are written only by the service role worker (bypasses RLS).
-- No browser INSERT / UPDATE / DELETE policies are created here.
-- ===========================================================================

ALTER TABLE public.ig_publish_attempts ENABLE ROW LEVEL SECURITY;

-- Remove dev-wide authenticated policies
DROP POLICY IF EXISTS "dev_select_attempts" ON public.ig_publish_attempts;
DROP POLICY IF EXISTS "dev_insert_attempts" ON public.ig_publish_attempts;

-- Remove any previous run of this migration's own policies (idempotency)
DROP POLICY IF EXISTS "admin_select_attempts" ON public.ig_publish_attempts;

CREATE POLICY "admin_select_attempts"
  ON public.ig_publish_attempts
  FOR SELECT
  TO authenticated
  USING (public.is_instaautopost_admin());

-- No browser INSERT / UPDATE / DELETE — service role only.

-- ===========================================================================
-- 4d. ig_schedule_slots — admin-only hardening
--
-- Service role bypasses RLS. Worker does not interact with schedule slots.
-- No delete policy introduced: no dev delete flow existed for this table.
-- Use slot_status = 'cancelled' instead of hard-deleting slots.
-- ===========================================================================

ALTER TABLE public.ig_schedule_slots ENABLE ROW LEVEL SECURITY;

-- Remove dev-wide authenticated policies
DROP POLICY IF EXISTS "authenticated users can select schedule slots" ON public.ig_schedule_slots;
DROP POLICY IF EXISTS "authenticated users can insert schedule slots" ON public.ig_schedule_slots;
DROP POLICY IF EXISTS "authenticated users can update schedule slots" ON public.ig_schedule_slots;

-- Remove any previous run of this migration's own policies (idempotency)
DROP POLICY IF EXISTS "admin_select_schedule_slots" ON public.ig_schedule_slots;
DROP POLICY IF EXISTS "admin_insert_schedule_slots" ON public.ig_schedule_slots;
DROP POLICY IF EXISTS "admin_update_schedule_slots" ON public.ig_schedule_slots;

CREATE POLICY "admin_select_schedule_slots"
  ON public.ig_schedule_slots
  FOR SELECT
  TO authenticated
  USING (public.is_instaautopost_admin());

CREATE POLICY "admin_insert_schedule_slots"
  ON public.ig_schedule_slots
  FOR INSERT
  TO authenticated
  WITH CHECK (public.is_instaautopost_admin());

CREATE POLICY "admin_update_schedule_slots"
  ON public.ig_schedule_slots
  FOR UPDATE
  TO authenticated
  USING  (public.is_instaautopost_admin())
  WITH CHECK (public.is_instaautopost_admin());

-- ===========================================================================
-- 5. Storage bucket hardening (instaautopost-media)
--
-- Public read is PRESERVED.
--   Instagram's Graph API fetches video_url at publish time; the URL must be
--   publicly accessible. Content is intended for public Instagram posts.
--   Non-guessable paths (UUID + timestamp) provide adequate obscurity.
--
-- Upload / update / delete are hardened from any-authenticated to admin-only.
--   The previous policies allowed any logged-in user to write to their own UUID
--   prefix. The new policies restrict writes to admins regardless of path.
--
-- Service role is not affected by storage RLS and is unaffected by these changes.
-- ===========================================================================

-- INSERT: admin-only upload
DROP POLICY IF EXISTS "instaautopost_media_authenticated_upload" ON storage.objects;
DROP POLICY IF EXISTS "instaautopost_media_admin_upload" ON storage.objects;
CREATE POLICY "instaautopost_media_admin_upload"
  ON storage.objects
  FOR INSERT
  TO authenticated
  WITH CHECK (
    bucket_id = 'instaautopost-media'
    AND public.is_instaautopost_admin()
  );

-- SELECT: public read — required for Instagram to fetch video_url at publish time
DROP POLICY IF EXISTS "instaautopost_media_public_read" ON storage.objects;
CREATE POLICY "instaautopost_media_public_read"
  ON storage.objects
  FOR SELECT
  TO public
  USING (bucket_id = 'instaautopost-media');

-- UPDATE: admin-only
DROP POLICY IF EXISTS "instaautopost_media_authenticated_update" ON storage.objects;
DROP POLICY IF EXISTS "instaautopost_media_admin_update" ON storage.objects;
CREATE POLICY "instaautopost_media_admin_update"
  ON storage.objects
  FOR UPDATE
  TO authenticated
  USING (
    bucket_id = 'instaautopost-media'
    AND public.is_instaautopost_admin()
  );

-- DELETE: admin-only
DROP POLICY IF EXISTS "instaautopost_media_authenticated_delete" ON storage.objects;
DROP POLICY IF EXISTS "instaautopost_media_admin_delete" ON storage.objects;
CREATE POLICY "instaautopost_media_admin_delete"
  ON storage.objects
  FOR DELETE
  TO authenticated
  USING (
    bucket_id = 'instaautopost-media'
    AND public.is_instaautopost_admin()
  );
