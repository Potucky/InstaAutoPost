-- InstaAutoPost Media Storage Bucket
-- Migration: 20260522000000_create_media_storage_bucket.sql
--
-- Purpose:
--   Create the instaautopost-media Storage bucket and its access policies.
--   Addresses the missing media storage bucket gap for InstaAutoPost.
--
-- Bucket visibility: PUBLIC
--
-- Why public:
--   Instagram's Graph API fetches the video file from the stored video_url
--   during publishing. The URL must be publicly accessible at publish time.
--   A private bucket would require signed URLs, which expire and cannot be
--   stored durably in ig_content_library.video_url ahead of a scheduled publish.
--   Public bucket + non-guessable object paths (user UUID + timestamp) is the
--   correct trade-off for this use case: content is intended for public Instagram
--   posts, and paths are not enumerable.
--
-- Security posture:
--   - Only authenticated users may upload, update, or delete objects.
--   - Upload is scoped to the uploading user's own UUID prefix (user_id/).
--   - Objects at any path are publicly readable (required for Instagram fetch).
--   - File paths include the user UUID + timestamp + sanitized filename;
--     they are non-guessable but not confidential.
--
-- Manual Supabase fallback:
--   If your Supabase project version does not support bucket creation via SQL
--   INSERT (some managed environments restrict storage.buckets writes), create
--   the bucket manually in the Supabase dashboard:
--     Storage > New Bucket > Name: instaautopost-media > Public: ON
--   Then apply the policy section of this migration separately.
--   The ON CONFLICT DO NOTHING guard makes the INSERT safe to re-run.
--
-- RLS note:
--   For a public bucket Supabase bypasses RLS on SELECT (downloads) automatically.
--   The SELECT policy below is included for explicit documentation and in case
--   bucket visibility is ever changed to private.
--
-- Idempotency:
--   DROP POLICY IF EXISTS before each CREATE POLICY makes this safe to re-run.
--   The bucket INSERT uses ON CONFLICT (id) DO NOTHING.

-- ---------------------------------------------------------------------------
-- Bucket
-- ---------------------------------------------------------------------------
INSERT INTO storage.buckets (id, name, public)
VALUES ('instaautopost-media', 'instaautopost-media', true)
ON CONFLICT (id) DO NOTHING;

-- ---------------------------------------------------------------------------
-- Storage RLS Policies
-- ---------------------------------------------------------------------------

-- INSERT: authenticated users may upload objects into their own UUID prefix only.
-- Object path must start with the uploader's auth.uid() as the first path segment.
-- Example valid path: "a1b2c3d4-...-uuid/1716000000000_my_reel.mp4"
DROP POLICY IF EXISTS "instaautopost_media_authenticated_upload" ON storage.objects;
CREATE POLICY "instaautopost_media_authenticated_upload"
ON storage.objects FOR INSERT
TO authenticated
WITH CHECK (
  bucket_id = 'instaautopost-media'
  AND (storage.foldername(name))[1] = (auth.uid())::text
);

-- SELECT: all requestors (including Instagram's fetch and unauthenticated browsers)
-- may read objects. Required: Instagram fetches video from this URL during publishing.
DROP POLICY IF EXISTS "instaautopost_media_public_read" ON storage.objects;
CREATE POLICY "instaautopost_media_public_read"
ON storage.objects FOR SELECT
TO public
USING (bucket_id = 'instaautopost-media');

-- UPDATE: authenticated users may update objects within their own UUID prefix.
DROP POLICY IF EXISTS "instaautopost_media_authenticated_update" ON storage.objects;
CREATE POLICY "instaautopost_media_authenticated_update"
ON storage.objects FOR UPDATE
TO authenticated
USING (
  bucket_id = 'instaautopost-media'
  AND (storage.foldername(name))[1] = (auth.uid())::text
);

-- DELETE: authenticated users may delete objects within their own UUID prefix.
DROP POLICY IF EXISTS "instaautopost_media_authenticated_delete" ON storage.objects;
CREATE POLICY "instaautopost_media_authenticated_delete"
ON storage.objects FOR DELETE
TO authenticated
USING (
  bucket_id = 'instaautopost-media'
  AND (storage.foldername(name))[1] = (auth.uid())::text
);
