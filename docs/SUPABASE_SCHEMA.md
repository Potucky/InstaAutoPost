# Supabase Schema Reference

## Authority And Drift Warning

This file documents the expected schema contract for InstaAutoPost. The live Supabase schema is the operational source of truth. Repo migrations must be kept aligned with the live database before real Instagram publishing.

Repo drift resolved (migration 20260516002000):

- `ig_publishing_queue.error_message` is dropped in migration 20260516002000.
- `ig_publishing_queue.failure_reason` and `worker_metadata` are added in migration 20260516002000.
- Worker and UI both use `failure_reason` for queue-level failure state.
- `error_message` remains valid only on `ig_publish_attempts`.

Migration 20260516002000 exists in repo and has been applied during dev/local verification. Confirm it is applied to the production Supabase instance before live publishing. Treat unconfirmed production state as a blocker before live publishing.

## Admin Allowlist

Migration `20260523001000_harden_admin_only_rls.sql` replaces development-wide authenticated RLS policies with admin-only policies backed by an allowlist table.

### `public.instaautopost_admins`

| Field | Purpose |
| --- | --- |
| `user_id` | Primary key; FK to `auth.users(id)` ON DELETE CASCADE. |
| `created_at` | Row creation timestamp. |

RLS is enabled. A SELECT policy allows admins to read the allowlist. No browser INSERT/UPDATE/DELETE policies exist — admin rows must be inserted manually via SQL.

### `public.is_instaautopost_admin()`

Helper function (SQL, STABLE, SECURITY DEFINER, search_path = public). Returns `true` when `auth.uid()` exists in `public.instaautopost_admins`. Used as the `USING`/`WITH CHECK` expression in all admin-only RLS policies. SECURITY DEFINER prevents RLS on the admins table from blocking the lookup.

### Adding the first admin UUID

Run this SQL in the Supabase dashboard SQL editor or psql (replace the placeholder with the real UUID from Authentication > Users):

```sql
INSERT INTO public.instaautopost_admins (user_id) VALUES ('YOUR_AUTH_USER_UUID');
```

Do not commit a real UUID to this file or to any migration.

### Access posture after migration 20260523001000

| Actor | Access |
| --- | --- |
| Browser (admin in allowlist) | Full access per table policies below. |
| Browser (authenticated, not in allowlist) | Blocked by all RLS policies. |
| Browser (unauthenticated) | Blocked. |
| Service role (worker / GitHub Actions) | Bypasses RLS entirely — unaffected. |
| `claim_next_queue_item()` RPC | SECURITY DEFINER — bypasses RLS — unaffected. |

Public signup remains disabled in the UI (Task 4.1). The allowlist check is the production safety net regardless of how a session was obtained.

## Current Tables

Implemented in repo migrations:

- `public.instaautopost_admins`
- `public.ig_content_library`
- `public.ig_publishing_queue`
- `public.ig_publish_attempts`
- `public.ig_schedule_slots`

Also implemented:

- `public.content_status` enum.
- `public.queue_status` enum.
- `public.attempt_status` enum.
- `public.claim_next_queue_item(p_worker_id TEXT)` RPC.
- `public.is_instaautopost_admin()` helper function.
- RLS enabled on all tables.
- Admin-only RLS policies (migration 20260523001000 replaces development-wide policies).

## `public.ig_content_library`

Repo migration fields:

| Field | Purpose |
| --- | --- |
| `id` | Primary key. |
| `title` | Content display title. |
| `caption` | Instagram caption text. |
| `video_url` | Publicly accessible video URL. |
| `thumbnail_url` | Optional thumbnail URL. |
| `hashtags` | Text array of hashtags. |
| `content_status` | `draft`, `approved`, or `archived`. |
| `media_type` | Media type, default `video`. |
| `duration_seconds` | Optional duration metadata. |
| `file_size` | Optional file size metadata. |
| `created_by` | Optional auth user reference. |
| `created_at` | Creation timestamp. |
| `updated_at` | Updated timestamp. |

## `public.ig_publishing_queue`

Known live fields:

| Field | Required Meaning |
| --- | --- |
| `queue_status` | Control state for scheduling and publishing. |
| `scheduled_at` | Publish trigger time. |
| `published_at` | Success timestamp; set only when published. |
| `external_media_id` | Instagram media ID; completion proof. |
| `attempt_count` | Number of claimed processing attempts. |
| `max_attempts` | Retry ceiling. |
| `next_retry_at` | Next eligible retry time. |
| `failure_reason` | Last queue-level failure reason. |
| `worker_metadata` | Worker-owned metadata for diagnostics and reconciliation. |
| `locked_at` | Worker lock timestamp. |
| `locked_by` | Worker ID that claimed the row. |
| `updated_at` | Last update timestamp. |

Repo migration currently also includes:

| Field | Status |
| --- | --- |
| `id` | Expected primary key. |
| `content_id` | Expected FK to `ig_content_library`. |
| `ig_user_id` | Present in migration; target account support. |
| `notes` | Present in migration. |
| `created_by` | Present in migration. |
| `created_at` | Present in migration. |
| `error_message` | Removed from queue table by migration 20260516002000. |

Required rule:

- Queue failure state belongs in `failure_reason`.

**Partial unique index (migration `20260523002000_prevent_duplicate_active_queue_rows.sql`)**:

Index name: `uidx_ig_publishing_queue_active_content_id`

Enforces at most one active queue row per `content_id`. Covers only active statuses: `scheduled`, `ready`, `processing`, `retry_scheduled`. Rows with terminal or draft statuses are not covered and do not block a future re-queue.

Pre-apply duplicate check — run this before applying the migration if the database has pre-existing data:

```sql
SELECT content_id, COUNT(*) AS active_count
FROM   public.ig_publishing_queue
WHERE  queue_status IN ('scheduled', 'ready', 'processing', 'retry_scheduled')
GROUP  BY content_id
HAVING COUNT(*) > 1;
```

If this query returns rows, resolve the duplicates (cancel or update conflicting rows) before running the migration. The migration's DO block will raise an exception and abort if duplicates exist.

Error code reference: Postgres raises `23505` (`unique_violation`) when an INSERT or UPDATE would create a second active row for the same `content_id`. UI and scripts should treat `23505` from `uidx_ig_publishing_queue_active_content_id` as "content is already queued". Handling this error code in the UI and worker is a follow-up task.

## `public.ig_publish_attempts`

Based on current migration and worker code:

| Field | Purpose |
| --- | --- |
| `id` | Primary key. |
| `queue_id` | FK to `ig_publishing_queue`. |
| `attempted_at` | Legacy attempt timestamp. Column exists in DB (DEFAULT NOW()) but is not used by the worker insert, UI, or TypeScript types. Use `created_at` instead. |
| `attempt_number` | Attempt sequence number. |
| `status` | `success`, `failed`, or `dry_run`. |
| `response_data` | Safe JSON response metadata. |
| `error_message` | Attempt-level error details, redacted. |
| `container_id` | Instagram container ID when available. |
| `media_id` | Instagram media ID when available. |
| `duration_ms` | Attempt duration. |
| `dry_run` | Boolean dry-run flag. |
| `worker_version` | Worker version string. |
| `created_at` | Canonical attempt timestamp. Used by the UI (`LogsAttempts`) for ordering and display, and typed in `PublishAttempt` in `ui/src/lib/types.ts`. |

`error_message` is acceptable here if the attempts table supports it.

## Expected Status Values

`queue_status` values in repo migration:

- `draft`
- `scheduled`
- `ready`
- `processing`
- `published`
- `failed`
- `cancelled`
- `retry_scheduled`

**Active statuses** — covered by `uidx_ig_publishing_queue_active_content_id`; at most one row per `content_id` may hold any of these at once:

- `scheduled`
- `ready`
- `processing`
- `retry_scheduled`

**Terminal statuses** — not covered by the unique index; a content item may be re-queued after reaching any of these:

- `published`
- `failed`
- `cancelled`

**`draft`** — not active; not covered by the unique index. A draft row does not block a second row from becoming active for the same content.

`attempt_status` values:

- `success`
- `failed`
- `dry_run`

## Expected Queue Transitions

Primary transitions:

```text
draft -> scheduled
scheduled -> processing -> published
scheduled -> processing -> failed
scheduled -> processing -> retry_scheduled
retry_scheduled -> processing -> published
retry_scheduled -> processing -> failed
retry_scheduled -> processing -> retry_scheduled
```

Optional transition:

```text
scheduled -> ready -> processing
```

Cancellation:

```text
draft/scheduled/ready/retry_scheduled/failed -> cancelled
```

Do not cancel or retry a row that already has completion proof.

## Fields That Must Not Be Used

- Do not use `ig_publishing_queue.error_message`.
- Do not rely on old project table names.
- Do not add generic JSON blobs for core state when typed queue columns exist.

## `public.ig_schedule_slots`

Migration `20260523000000_create_ig_schedule_slots.sql` adds:

| Field | Purpose |
| --- | --- |
| `id` | Primary key (gen_random_uuid). |
| `slot_date` | Local America/New_York posting calendar date (YYYY-MM-DD). Used for calendar grouping; compare as a string, not via `new Date()`. |
| `slot_window` | `morning`, `lunch`, or `evening`. |
| `scheduled_at` | Exact UTC timestamptz publish instant. Use for time display, upcoming filtering, and ordering. Do not use to determine the calendar day. |
| `content_id` | FK to `ig_content_library`; null when empty. Unique across active statuses (assigned, queued). |
| `queue_id` | FK to `ig_publishing_queue`; null until linked. Unique where not null. |
| `slot_status` | `empty`, `assigned`, `queued`, `published`, `failed`, or `cancelled`. |
| `notes` | Optional free-text note. |
| `created_at` | Creation timestamp. |
| `updated_at` | Auto-updated on any row change. |

**Purpose**: user-facing calendar/schedule plan. `ig_publishing_queue` remains the worker queue. Slots start as `empty`; content and queue rows are assigned in a separate step.

**Frontend calendar grouping rule**: group slots by `slot_date` string equality (e.g. `slot.slot_date === 'YYYY-MM-DD'`). Do not parse `slot_date` via `new Date(slot_date)` for grouping — JavaScript UTC date-only parsing shifts dates for users west of UTC. Filter the month query using `slot_date` (`.gte`/`.lte` on the `YYYY-MM-DD` string). Use `scheduled_at` only for exact-time display and ordering within a day.

**Indexes**: `slot_date`, `scheduled_at`, `slot_status`, `content_id`, `queue_id`.

**Constraints** (after migration `20260523003000_sync_schedule_slots_with_queue_lifecycle.sql`):

| Constraint | Definition | Purpose |
| --- | --- | --- |
| `ig_schedule_slots_scheduled_at_unique` | `UNIQUE (scheduled_at)` | One slot per exact publish moment. |
| `uidx_ig_schedule_slots_active_content_id` | Partial unique on `content_id WHERE content_id IS NOT NULL AND slot_status IN ('assigned','queued')` | At most one active slot per content item. Terminal slots (published, failed, cancelled) do not block re-scheduling. Replaces the former global `ig_schedule_slots_content_id_unique` index. |
| `uidx_ig_schedule_slots_queue_id` | Partial unique on `queue_id WHERE queue_id IS NOT NULL` | Each queue row is linked to at most one slot. |

**RLS**: enabled; admin-only policies (migration `20260523001000_harden_admin_only_rls.sql`) restrict browser select, insert, and update to users in `public.instaautopost_admins`. No delete policy — use `slot_status = 'cancelled'` instead of hard-deleting slots.

**Queue linkage and lifecycle sync (migration `20260523003000_sync_schedule_slots_with_queue_lifecycle.sql`)**:

`ig_publishing_queue` is the lifecycle source of truth. `ig_schedule_slots` is a calendar projection — it reflects queue state but does not drive it.

*queue_id link contract*: a slot is linked by setting `slot.queue_id = queue.id`. Once linked, the trigger `trg_sync_slot_with_queue_lifecycle` (AFTER INSERT OR UPDATE on `ig_publishing_queue`) automatically updates the slot's `content_id`, `scheduled_at`, `slot_date`, `slot_status`, and `updated_at`. `slot_window` is never modified by the trigger — it is the user's scheduling choice.

*Derived slot_status mapping*:

| Queue state | Derived `slot_status` |
| --- | --- |
| `published_at IS NOT NULL` or `external_media_id IS NOT NULL` | `published` |
| `queue_status = 'failed'` | `failed` |
| `queue_status = 'cancelled'` | `cancelled` |
| All other queue statuses | `queued` |

*failed / cancelled are marked, not auto-released*: when a queue row reaches `failed` or `cancelled`, the linked slot is marked accordingly. The slot is NOT automatically released back to `assigned` or `empty`. An operator or future app task must explicitly re-assign content if a retry is desired.

*Published proof stays on `ig_publishing_queue`*: `published_at` and `external_media_id` are set only on the queue row. `slot_status = 'published'` is a projection only — do not use slot status as publishing proof.

*Re-queue semantics*: the `uidx_ig_schedule_slots_active_content_id` partial index covers only `assigned` and `queued` statuses. A content item whose previous slot reached a terminal status may be assigned to a new slot without violating the index.

*Follow-up task*: creating a queue row from an assigned slot and linking them atomically (setting `slot.queue_id` and inserting the queue row in the same transaction) is an application-level operation for a later task.

## Storage Bucket

Migration `20260522000000_create_media_storage_bucket.sql` adds:

| Item | Value |
| --- | --- |
| Bucket name | `instaautopost-media` |
| Visibility | **Public** |
| Object path pattern | `{user.id}/{uuid}_{sanitized_filename}` |

**Why public**: Instagram's Graph API must fetch the video from `video_url` at publish time. Signed URLs from a private bucket expire before a scheduled publish and cannot be stored durably. Public bucket with non-guessable paths (UUID + sanitized filename) is the correct trade-off for content intended to be publicly posted anyway.

**Upload/update/delete policy**: Only admin users (in `public.instaautopost_admins`) may upload, update, or delete objects. Hardened from any-authenticated in migration `20260523001000_harden_admin_only_rls.sql`.

**Upload validation (UI)**:

| Rule | Value |
| --- | --- |
| Accepted format | MP4 only (`video/mp4` or `.mp4` extension when `file.type` is empty) |
| Maximum file size | 45 MB (`MAX_VIDEO_UPLOAD_BYTES = 45 * 1024 * 1024`) |
| Empty file | Rejected |
| Missing user session | Rejected — anonymous path fallback removed |
| Storage path | `{user.id}/{uuid}_{sanitized_filename}` (`crypto.randomUUID()` when available; UUID-compatible fallback otherwise) |

Validation is enforced in `ui/src/pages/UploadVideo.tsx` before any upload attempt. Non-MP4, empty, oversized, and unauthenticated upload attempts show a user-facing `uploadError` and do not call Supabase Storage.

**Best-effort orphan cleanup (UI)**:

An "orphan" is a Storage object whose path is not referenced by any `ig_content_library.video_url` row. Orphans can appear if a file is uploaded but the subsequent DB insert fails, or if the user clears/cancels before saving.

The UI performs a best-effort cleanup in two situations:

1. **DB insert failure**: if the uploaded public URL still matches the form `video_url`, the UI queries `ig_content_library` for that URL. If no row references it, the uploaded object is removed. If the lookup or removal fails, the original DB error is preserved and a short note ("Storage cleanup may be needed") is appended.
2. **Clear uploaded file (X button) or Cancel**: same guard — queries the content library before removing. State is cleared immediately; the removal runs in the background.

Cleanup is best-effort only. It is not a substitute for periodic orphan detection.

**Orphan detection script**: `scripts/admin/report_orphan_storage_files.py` — report-only, no deletion. Lists Storage objects older than a configurable grace period (default: 24h) whose paths do not appear in any `ig_content_library` row. Outputs a plain-text report and prints "No files deleted; report only." Test-import carousel secondary images may appear as intentional unlinked objects.

**Destructive cleanup**: not implemented. Any bulk deletion of orphan objects must be a future explicit reviewed operation, implemented as a separate script and run only after pre-flight verification.

**Manual Supabase step required**: Apply this migration in the Supabase dashboard SQL editor, or if bucket creation via SQL INSERT is blocked by the managed environment, create the bucket manually (Storage > New Bucket > Name: `instaautopost-media` > Public: ON) and then apply only the policy statements.

## Migration Safety Rules

- Never edit an already-applied production migration to hide drift.
- Add a new migration for schema changes.
- Verify live columns before changing worker writes.
- Keep docs, TypeScript types, worker code, and migrations aligned.
- Include RLS and RPC permission implications in migration review.
- Test dry-run after schema changes before any live run.

## SQL Checklist Before Live Publish

Before first real publish:

- [ ] Confirm `ig_publishing_queue.failure_reason` exists.
- [ ] Confirm `ig_publishing_queue.worker_metadata` exists if worker/docs rely on it.
- [ ] Confirm `ig_publishing_queue.error_message` is not used by code or UI.
- [ ] Confirm `ig_publish_attempts.error_message` exists if worker inserts it.
- [ ] Confirm `claim_next_queue_item` can handle stale `processing` rows or a separate recovery path exists.
- [ ] Confirm `published_at` and `external_media_id` are both set on success.
- [ ] Confirm service role can execute the claim RPC.
- [ ] Confirm anon/authenticated users cannot execute worker-only RPCs.
- [ ] Confirm RLS policies match current environment.
- [ ] Confirm migration `20260523001000_harden_admin_only_rls.sql` is applied.
- [ ] Confirm `public.instaautopost_admins` has at least one admin UUID inserted.
- [ ] Confirm `public.is_instaautopost_admin()` returns `true` for the admin browser session.
- [ ] Confirm service role worker still reads/writes queue and attempts without RLS errors.
- [ ] Confirm migration `20260523002000_prevent_duplicate_active_queue_rows.sql` is applied.
- [ ] Confirm `uidx_ig_publishing_queue_active_content_id` index exists on `ig_publishing_queue`.
- [ ] Run pre-apply duplicate check query; confirm zero rows before applying if data exists.
- [ ] Confirm migration `20260523003000_sync_schedule_slots_with_queue_lifecycle.sql` is applied.
- [ ] Confirm `uidx_ig_schedule_slots_active_content_id` exists; `ig_schedule_slots_content_id_unique` is dropped.
- [ ] Confirm `uidx_ig_schedule_slots_queue_id` exists on `ig_schedule_slots`.
- [ ] Confirm `trg_sync_slot_with_queue_lifecycle` trigger exists on `ig_publishing_queue`.
- [ ] Confirm `derive_slot_status_from_queue()` and `sync_slot_with_queue_lifecycle()` functions exist.
- [ ] Confirm publisher workflow concurrency is configured (`group: instaautopost-publisher`, `cancel-in-progress: false`) in `.github/workflows/instaautopost-publisher.yml`.
- [ ] Confirm single `publish` job is present in the workflow (no `publish_dry_run` / `publish_live` split).
- [ ] Confirm workflow sets `INSTAGRAM_API_ENABLED=true` for production runs; no `live_mode` or `live_confirmation` inputs exist.
- [ ] Confirm optional `queue_id` is the only `workflow_dispatch` input.
- [ ] Confirm safety relies on queue eligibility checks, concurrency group, one item per run, duplicate publish protection (`external_media_id` anchor), and required GitHub secrets — not an environment gate.

## Manual Script Safety Note

Scripts in `scripts/admin/` can mutate scheduling and queue tables when `--execute` is passed:

- `generate_schedule_slots.py` — inserts rows into `ig_schedule_slots`.
- `assign_content_to_schedule_slots.py` — updates `content_id` and `slot_status` on `ig_schedule_slots`.
- `schedule_draft_content.py` — inserts rows into `ig_publishing_queue`.

All three are dry-run by default. Verify `SUPABASE_URL` points to the intended Supabase project before using `--execute`.

Scripts in `scripts/local/` that can mutate Supabase:

- `import_travel_test_batch.py` — uploads files to Supabase Storage and inserts rows into `ig_content_library` with `--execute`. Must not target production unless a test import is explicitly intended.
- `fix_video_post_002.py` — uploads one file to Supabase Storage and inserts one row into `ig_content_library` with `--execute`. Must not target production unless explicitly intended.

No script in `scripts/admin/` or `scripts/local/` publishes to Instagram or triggers GitHub Actions. The GitHub Actions publisher workflow calls only `scripts/instaautopost_publisher.py`.
