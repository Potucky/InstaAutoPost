# Supabase Schema Reference

## Authority And Drift Warning

This file documents the expected schema contract for InstaAutoPost. The live Supabase schema is the operational source of truth. Repo migrations must be kept aligned with the live database before real Instagram publishing.

Repo drift resolved (migration 20260516002000):

- `ig_publishing_queue.error_message` is dropped in migration 20260516002000.
- `ig_publishing_queue.failure_reason` and `worker_metadata` are added in migration 20260516002000.
- Worker and UI both use `failure_reason` for queue-level failure state.
- `error_message` remains valid only on `ig_publish_attempts`.

Migration 20260516002000 exists in repo and has been applied during dev/local verification. Confirm it is applied to the production Supabase instance before live publishing. Treat unconfirmed production state as a blocker before live publishing.

## Current Tables

Implemented in repo migrations:

- `public.ig_content_library`
- `public.ig_publishing_queue`
- `public.ig_publish_attempts`
- `public.ig_schedule_slots`

Also implemented:

- `public.content_status` enum.
- `public.queue_status` enum.
- `public.attempt_status` enum.
- `public.claim_next_queue_item(p_worker_id TEXT)` RPC.
- RLS enabled on all three tables.
- Development RLS policies for authenticated users.

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

## `public.ig_publish_attempts`

Based on current migration and worker code:

| Field | Purpose |
| --- | --- |
| `id` | Primary key. |
| `queue_id` | FK to `ig_publishing_queue`. |
| `attempted_at` | Attempt timestamp. |
| `attempt_number` | Attempt sequence number. |
| `status` | `success`, `failed`, or `dry_run`. |
| `response_data` | Safe JSON response metadata. |
| `error_message` | Attempt-level error details, redacted. |
| `container_id` | Instagram container ID when available. |
| `media_id` | Instagram media ID when available. |
| `duration_ms` | Attempt duration. |
| `dry_run` | Boolean dry-run flag. |
| `worker_version` | Worker version string. |
| `created_at` | Creation timestamp. |

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
| `slot_date` | Calendar date of the slot. |
| `slot_window` | `morning`, `lunch`, or `evening`. |
| `scheduled_at` | Exact UTC timestamptz for this slot (unique). |
| `content_id` | FK to `ig_content_library`; null when empty. Unique where not null. |
| `queue_id` | FK to `ig_publishing_queue`; null until queued. |
| `slot_status` | `empty`, `assigned`, `queued`, `published`, `failed`, or `cancelled`. |
| `notes` | Optional free-text note. |
| `created_at` | Creation timestamp. |
| `updated_at` | Auto-updated on any row change. |

**Purpose**: user-facing calendar/schedule plan. `ig_publishing_queue` remains the worker queue. Slots start as `empty`; content and queue rows are assigned in a separate step.

**Indexes**: `slot_date`, `scheduled_at`, `slot_status`, `content_id`, `queue_id`.

**Constraints**: `UNIQUE (scheduled_at)`; partial unique index on `content_id WHERE content_id IS NOT NULL`.

**RLS**: enabled; development policies allow authenticated users to select, insert, and update.

## Storage Bucket

Migration `20260522000000_create_media_storage_bucket.sql` adds:

| Item | Value |
| --- | --- |
| Bucket name | `instaautopost-media` |
| Visibility | **Public** |
| Object path pattern | `{user_uuid}/{timestamp}_{sanitized_filename}` |

**Why public**: Instagram's Graph API must fetch the video from `video_url` at publish time. Signed URLs from a private bucket expire before a scheduled publish and cannot be stored durably. Public bucket with non-guessable paths (UUID + timestamp) is the correct trade-off for content intended to be publicly posted anyway.

**Upload policy**: Only authenticated users may upload/update/delete objects, scoped to their own UUID prefix via `(storage.foldername(name))[1] = auth.uid()::text`.

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
