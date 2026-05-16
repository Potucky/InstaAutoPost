# InstaAutoPost Factory — Architecture Reference

## Overview

InstaAutoPost is an Instagram autoposting control center. It separates concerns cleanly:

- **UI**: Content management and queue scheduling — zero publishing logic.
- **Backend Worker**: Owns all Instagram Graph API calls.
- **Supabase**: Single source of truth. Every state transition is recorded.
- **GitHub Actions**: Cron scheduler that triggers the worker on a 5-minute interval.

---

## Core Architecture Principles

### 1. Content Library

`public.ig_content_library` stores all video content metadata. A record in this table represents a publishable asset: title, caption, video URL, hashtags, and status (`draft` → `approved` → `archived`).

Content is never deleted — it is archived. This preserves the publish history link from `ig_publishing_queue`.

### 2. Publishing Queue

`public.ig_publishing_queue` is the scheduling ledger. Each row represents one scheduled publish intent:

- `content_id` → links to the content asset
- `scheduled_at` → when to publish (the trigger)
- `queue_status` → the control field (see state machine below)
- `published_at` + `external_media_id` → completion proof (set only on success)

**Queue Status State Machine:**

```
draft
  └─► scheduled    (user sets scheduled_at and moves to scheduled)
        └─► ready  (worker picks up items where scheduled_at <= now())
              └─► processing  (worker locks the row)
                    ├─► published        (success path)
                    ├─► retry_scheduled  (transient failure, attempt_count < max)
                    └─► failed           (terminal failure, attempt_count >= max)
```

`cancelled` is a terminal state reachable from any non-published status via UI action.

### 3. Scheduler

GitHub Actions runs `.github/workflows/instaautopost-publisher.yml` every 5 minutes via cron (`*/5 * * * *`). Each workflow execution runs the publisher worker once. The worker processes exactly one queue item per run.

### 4. Publisher Worker

`scripts/instaautopost_publisher.py` is the only component that calls the Instagram Graph API.

**Execution flow per run:**

1. Connect to Supabase using service role key.
2. Call `claim_next_queue_item(worker_id)` — an atomic PostgreSQL function that selects and locks one due item using `FOR UPDATE SKIP LOCKED`.
3. If no item is due → exit cleanly (nothing to do).
4. Fetch associated content from `ig_content_library`.
5. Check `INSTAGRAM_API_ENABLED` environment variable:
   - If `false` (default) → **dry-run mode**: simulate the flow, log a `dry_run` attempt, exit.
   - If `true` → **live mode**: execute the full Instagram publish flow.
6. Live mode steps:
   a. `POST /{ig-user-id}/media` → create media container, receive `container_id`.
   b. `GET /{container_id}?fields=status_code` → poll until `FINISHED` (max 12 attempts, 5s apart).
   c. `POST /{ig-user-id}/media_publish` → publish the container, receive `media_id`.
7. On success: set `published_at`, `external_media_id`, `queue_status = published`.
8. On failure: log error, increment `attempt_count`. If under `max_attempts` → set `retry_scheduled` with exponential backoff. If at limit → set `failed`.
9. Always write one row to `ig_publish_attempts`.

**Safety invariants:**
- Never call publish if `published_at IS NOT NULL`.
- Never call publish if `external_media_id IS NOT NULL`.
- Row locking prevents concurrent duplicate processing.
- Stale locks (older than 10 minutes) are reclaimed automatically.

### 5. Retry System

Retry scheduling uses exponential backoff:

| Attempt | Backoff |
|---------|---------|
| 1 → retry | 5 minutes |
| 2 → retry | 10 minutes |
| 3 → retry | 20 minutes |
| ≥ max_attempts | `failed` (terminal) |

`max_attempts` defaults to 3 and is configurable per queue row.

### 6. Token Management

Instagram access tokens must be long-lived tokens (60 days). Token rotation is manual — set `IG_ACCESS_TOKEN` in GitHub Secrets before expiry.

TODO: Automate token refresh via a scheduled GitHub Actions job calling the Instagram token refresh endpoint.

### 7. Analytics / Logs

`public.ig_publish_attempts` records every attempt (including dry runs). This table is the audit log.

Fields:
- `status`: `success | failed | dry_run`
- `dry_run`: boolean flag
- `container_id`: Instagram container ID (live mode)
- `media_id`: Instagram media ID (on success)
- `duration_ms`: end-to-end processing time
- `response_data`: raw Instagram API response (JSONB)
- `worker_version`: for tracing across worker deployments

### 8. Supabase-First Architecture

All state lives in Supabase. The worker is stateless — it reads from and writes to Supabase only. This means:

- Multiple workers can run safely (row locking prevents conflicts).
- Retries are driven by database state, not in-memory queues.
- The UI always shows current state with no caching layer.
- Supabase Realtime can be added to push live updates to the dashboard.

### 9. No Random File Publishing

The worker only publishes items that are explicitly in the queue with `queue_status IN ('ready', 'scheduled', 'retry_scheduled')` and `scheduled_at <= NOW()`. There is no file-system scanning or ad-hoc triggering.

### 10. Dashboard-Ready Foundation

All tables are designed for simple Supabase client queries from the UI:
- `ig_publishing_queue` joins to `ig_content_library` via `content_id`
- `ig_publish_attempts` joins to `ig_publishing_queue` via `queue_id`
- Indexes on `queue_status`, `scheduled_at`, `published_at` cover all dashboard query patterns

---

## Database Tables

### `public.ig_content_library`

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `title` | TEXT | Display title |
| `caption` | TEXT | Instagram caption |
| `video_url` | TEXT | Publicly accessible video URL |
| `thumbnail_url` | TEXT | Optional thumbnail |
| `hashtags` | TEXT[] | Array of hashtags |
| `content_status` | ENUM | `draft / approved / archived` |
| `media_type` | TEXT | `video` (default) |
| `duration_seconds` | INTEGER | Video duration |
| `file_size` | BIGINT | File size in bytes |
| `created_by` | UUID | Auth user reference |
| `created_at` | TIMESTAMPTZ | |
| `updated_at` | TIMESTAMPTZ | Auto-updated |

### `public.ig_publishing_queue`

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `content_id` | UUID | FK → ig_content_library |
| `queue_status` | ENUM | `draft/scheduled/ready/processing/published/failed/cancelled/retry_scheduled` |
| `scheduled_at` | TIMESTAMPTZ | Publish trigger time |
| `published_at` | TIMESTAMPTZ | Set on success only |
| `external_media_id` | TEXT | Instagram media ID (completion proof) |
| `attempt_count` | INTEGER | Times processing was attempted |
| `max_attempts` | INTEGER | Retry ceiling (default 3) |
| `next_retry_at` | TIMESTAMPTZ | When to retry after failure |
| `error_message` | TEXT | Last error |
| `ig_user_id` | TEXT | Target Instagram user ID |
| `locked_at` | TIMESTAMPTZ | Worker lock timestamp |
| `locked_by` | TEXT | Worker instance ID |
| `notes` | TEXT | Optional notes |
| `created_by` | UUID | Auth user reference |

### `public.ig_publish_attempts`

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `queue_id` | UUID | FK → ig_publishing_queue |
| `attempted_at` | TIMESTAMPTZ | When the attempt started |
| `attempt_number` | INTEGER | Attempt sequence number |
| `status` | ENUM | `success / failed / dry_run` |
| `response_data` | JSONB | Raw API response |
| `error_message` | TEXT | Error details |
| `container_id` | TEXT | Instagram container ID |
| `media_id` | TEXT | Instagram media ID |
| `duration_ms` | INTEGER | Processing duration |
| `dry_run` | BOOLEAN | Was this a dry run |
| `worker_version` | TEXT | Worker version string |

---

## Environment Variables

### Worker (GitHub Actions Secrets)

| Name | Required | Description |
|------|----------|-------------|
| `SUPABASE_URL` | Yes | Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Yes | Service role key |
| `IG_USER_ID` | Live only | Instagram Business User ID |
| `IG_ACCESS_TOKEN` | Live only | Long-lived access token |
| `INSTAGRAM_API_ENABLED` | No | `true` to enable live publishing (default: dry-run) |

### UI (Browser)

| Name | Required | Description |
|------|----------|-------------|
| `VITE_SUPABASE_URL` | Yes | Supabase project URL |
| `VITE_SUPABASE_ANON_KEY` | Yes | Anon key (public, safe for browser) |

> The service role key is **never** used in the frontend.

---

## Security Model

- **Frontend** uses `anon` key + RLS policies. Dev policies allow all authenticated users. Production policies should restrict to `auth.uid() = created_by`.
- **Worker** uses `service_role` key, which bypasses RLS. It runs in GitHub Actions (trusted environment).
- **Row locking** via `claim_next_queue_item()` PostgreSQL function prevents duplicate publishing.
- **Completion guards**: worker checks `published_at IS NULL` and `external_media_id IS NULL` before any API call.
