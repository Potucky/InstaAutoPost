-- InstaAutoPost — Development RLS Policies
-- File: supabase/policies/instaautopost_dev_rls_policies.sql
--
-- These policies allow all authenticated users full access to all tables.
-- Replace with owner-scoped policies before going to production:
--   USING (auth.uid() = created_by)
--
-- Apply via Supabase Dashboard SQL editor or `supabase db push`.

-- ---------------------------------------------------------------------------
-- ig_content_library
-- ---------------------------------------------------------------------------
CREATE POLICY "dev_select_content"
  ON public.ig_content_library
  FOR SELECT
  TO authenticated
  USING (true);

CREATE POLICY "dev_insert_content"
  ON public.ig_content_library
  FOR INSERT
  TO authenticated
  WITH CHECK (true);

CREATE POLICY "dev_update_content"
  ON public.ig_content_library
  FOR UPDATE
  TO authenticated
  USING (true)
  WITH CHECK (true);

-- DEV ONLY — remove entirely before production.
-- WARNING: ig_content_library is designed to be archive-only (set content_status = 'archived').
-- This policy exists only so local dev tooling can reset test data. Never open in production.
CREATE POLICY "dev_delete_content"
  ON public.ig_content_library
  FOR DELETE
  TO authenticated
  USING (auth.uid() = created_by);

-- ---------------------------------------------------------------------------
-- ig_publishing_queue
-- ---------------------------------------------------------------------------
CREATE POLICY "dev_select_queue"
  ON public.ig_publishing_queue
  FOR SELECT
  TO authenticated
  USING (true);

CREATE POLICY "dev_insert_queue"
  ON public.ig_publishing_queue
  FOR INSERT
  TO authenticated
  WITH CHECK (true);

CREATE POLICY "dev_update_queue"
  ON public.ig_publishing_queue
  FOR UPDATE
  TO authenticated
  USING (true)
  WITH CHECK (true);

-- DEV ONLY — remove entirely before production.
-- Allows a user to delete only their own queue rows, and only when the row is not
-- in an active/terminal state. This is valid PostgreSQL/Supabase RLS syntax;
-- NOT IN with multiple literals is legal inside a USING expression.
-- Production note: prefer setting queue_status = 'cancelled' over hard-deleting rows
-- so that ig_publish_attempts audit history is preserved via the ON DELETE CASCADE chain.
CREATE POLICY "dev_delete_queue"
  ON public.ig_publishing_queue
  FOR DELETE
  TO authenticated
  USING (
    auth.uid() = created_by
    AND queue_status NOT IN ('processing', 'retry_scheduled', 'published')
  );

-- ---------------------------------------------------------------------------
-- ig_publish_attempts
-- ---------------------------------------------------------------------------
CREATE POLICY "dev_select_attempts"
  ON public.ig_publish_attempts
  FOR SELECT
  TO authenticated
  USING (true);

CREATE POLICY "dev_insert_attempts"
  ON public.ig_publish_attempts
  FOR INSERT
  TO authenticated
  WITH CHECK (true);

-- Attempts are append-only — no update or delete policies

-- ---------------------------------------------------------------------------
-- Note: service_role bypasses RLS automatically (used by publisher worker).
-- No additional grants needed for the backend worker.
-- ---------------------------------------------------------------------------
