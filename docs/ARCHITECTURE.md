# InstaAutoPost Architecture

## Overview

InstaAutoPost separates the dashboard, database, worker, scheduler, and Instagram Graph API into clear boundaries.

- Frontend/control center: Vite, React, and TypeScript UI.
- Backend state: Supabase PostgreSQL.
- Publishing control: queue tables and status transitions.
- Worker: Python script at `scripts/instaautopost_publisher.py`.
- Automation: GitHub Actions workflow at `.github/workflows/instaautopost-publisher.yml`.
- External API: Instagram Graph API.

The UI manages content and queue state. The worker is the only component that should call Instagram publishing endpoints.

## System Boundaries

### UI Boundary

The UI may:

- Create and update content records.
- Create and update queue records.
- Show calendar, queue, attempt logs, and dashboard state.
- Surface safety status.

The UI must not:

- Store service role secrets.
- Call the Instagram Graph API.
- Publish directly.
- Hide failed or stuck worker states.

### Supabase Boundary

Supabase is the system of record for:

- Content metadata.
- Queue state.
- Publish attempts.
- Locking state.
- Completion proof.

### Worker Boundary

The Python worker may:

- Use the Supabase service role key.
- Claim one due queue row.
- Read content for the queue row.
- Run dry-run logic.
- Call Instagram Graph API in live mode only.
- Write publish attempts.
- Update queue status.

The worker must not:

- Publish outside the queue.
- Publish when live mode is not explicitly enabled.
- Retry after a known successful Instagram publish without manual reconciliation.

### GitHub Actions Boundary

GitHub Actions installs dependencies and runs the worker. Automatic schedule is currently disabled. Manual `workflow_dispatch` remains available.

## Data Flow

```text
Operator
  |
  v
React Control Center
  |
  | anon key + RLS
  v
Supabase
  |  ig_content_library
  |  ig_publishing_queue
  |  ig_publish_attempts
  |
  | service role key
  v
Python Publisher Worker
  |
  | live mode only when INSTAGRAM_API_ENABLED=true
  v
Instagram Graph API
  |
  v
Instagram Media / Published Post
```

## Queue-Based Publishing

Publishing begins with a row in `public.ig_publishing_queue`.

Expected high-level transition:

```text
scheduled
  -> processing
  -> published

scheduled
  -> processing
  -> retry_scheduled

scheduled
  -> processing
  -> failed
```

The schema also contains `draft`, `ready`, and `cancelled` states in the repo migration. The claim function currently considers `ready`, `scheduled`, and `retry_scheduled` actionable.

## Dry-Run Flow

```text
Start worker
  -> read SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY
  -> claim one due queue item
  -> fetch linked content
  -> detect INSTAGRAM_API_ENABLED is not true
  -> write dry_run attempt
  -> reset queue item back to scheduled
  -> clear lock fields
  -> exit
```

Dry-run must not call Instagram. It may still write to Supabase and adjust queue lock state.

## Live Publish Flow

```text
Start worker
  -> connect to Supabase
  -> claim one due queue item
  -> fetch linked content
  -> require IG_USER_ID and IG_ACCESS_TOKEN
  -> create Instagram media container
  -> poll container until FINISHED
  -> publish media container
  -> receive media_id
  -> record attempt
  -> mark queue published with published_at and external_media_id
```

Active safety concern: live environment variables should be validated before claiming a queue row, so a missing `IG_USER_ID` or `IG_ACCESS_TOKEN` cannot leave a row stuck in `processing`.

## Failure And Retry Flow

Current worker intent:

```text
failure before media_id
  -> write failed attempt
  -> if attempt_count < max_attempts: retry_scheduled
  -> else: failed
```

Required safety improvement:

```text
media_id returned by Instagram
  -> do not schedule retry on later DB/logging failure
  -> mark as manual reconciliation needed or preserve completion proof
```

Once Instagram returns a real media ID, treating a later local error as retryable can create duplicate publishing risk.

## Duplicate Publishing Protection Principles

- Completion proof is `published_at` plus `external_media_id`.
- The worker must skip rows with either completion proof field already set.
- Queue claiming must be atomic and lock-based.
- A returned Instagram `media_id` must change the failure model from retryable to reconciliation-required.
- Attempts should be append-only audit records.
- GitHub Actions concurrency and schedule settings should avoid overlapping live publisher runs when automation is restored.

## Current Automation State

The workflow file is `.github/workflows/instaautopost-publisher.yml`.

Implemented:

- Manual `workflow_dispatch`.
- Python setup and dependency install.
- Worker run command.

Currently disabled:

- Automatic cron schedule, commented out to stop failure email spam.

Restore automation only after worker safety blockers are fixed and the user explicitly asks.

