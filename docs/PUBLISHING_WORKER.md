# Publishing Worker Reference

## Script

Main worker:

```text
scripts/instaautopost_publisher.py
```

The worker processes one due queue item per execution.

## Environment Variables

Always required:

- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`

Required only for live publishing:

- `IG_USER_ID`
- `IG_ACCESS_TOKEN`

Live gate:

- `INSTAGRAM_API_ENABLED`

Behavior:

- The value is trimmed and lowercased before comparison. Any value that does not lowercase to `true` means dry-run mode.
- `INSTAGRAM_API_ENABLED=true` (or `TRUE`, `True`) enables live mode.
- Recommended safety value when not publishing: set to `false` or leave unset.

Do not print values for secrets or tokens.

## Dry-Run Behavior

Current intent:

```text
connect to Supabase
claim one due queue row
fetch content
do not call Instagram
write a dry_run attempt
reset queue row to scheduled
decrement attempt_count back to prior value
clear lock fields
clear failure_reason
exit
```

Dry-run is safe from Instagram publishing because the code path does not call the Instagram API when `INSTAGRAM_API_ENABLED` is not true.

Dry-run still changes Supabase state temporarily and writes an attempt record.

## Live Behavior

Implemented:

```text
connect to Supabase
validate IG_USER_ID and IG_ACCESS_TOKEN (exit before claim if missing)
claim one due queue row
fetch content
create media container
poll container status
publish media container
receive media_id
anchor external_media_id + published_at atomically (_anchor_media_id)
write success attempt
mark queue row published (final confirmation write)
```

## Queue Claim Behavior

The worker calls:

```text
claim_next_queue_item(p_worker_id)
```

The repo migration claim function selects rows where:

- `queue_status` is `ready`, `scheduled`, or `retry_scheduled`.
- `scheduled_at <= NOW()`.
- `published_at IS NULL`.
- `external_media_id IS NULL`.
- `attempt_count < max_attempts`.
- `next_retry_at` is null or due.
- `locked_at` is null or older than 10 minutes.

It then sets:

- `queue_status = processing`
- `locked_at = NOW()`
- `locked_by = p_worker_id`
- `attempt_count = attempt_count + 1`

Stale processing recovery (fixed in migration 20260516002000):

- The updated claim function also selects `processing` rows where `locked_at` is older than 10 minutes. These are treated as abandoned and reclaimed as a new attempt.
- Rows at `max_attempts` cannot be auto-reclaimed; an operator must reset or cancel them manually.

## Lock And Unlock Rules

Implemented rules:

- Every claimed row reaches a terminal, retry, published, or unlocked state.
- Content fetch failure after claim calls `mark_failed_or_retry()` — row is never left stuck.
- Live env var failure exits before claiming — row is never touched.
- Failures before an Instagram API call clear locks and set `failed` or `retry_scheduled`.
- Dry-run clears locks before exit.
- Stale `processing` rows (lock > 10 min) are reclaimed by the updated claim function.

## Retry Rules

Current retry backoff:

| Attempt | Backoff |
| --- | --- |
| 1 | 5 minutes |
| 2 | 10 minutes |
| 3+ | 20 minutes fallback |

Current transition intent:

```text
processing -> retry_scheduled, when attempt_count < max_attempts
processing -> failed, when attempt_count >= max_attempts
```

Do not retry after a confirmed Instagram `media_id` without manual reconciliation.

## Failure Handling

Failure before `media_id`:

- Write failed attempt if possible.
- Store redacted error in `failure_reason`.
- Clear lock fields.
- Retry or fail based on attempt count.

Failure after `media_id` (implemented):

- Immediately after `ig_publish()` returns `media_id`, `_anchor_media_id()` atomically writes `external_media_id`, `published_at`, `queue_status = 'published'`, and a `post_publish_reconciliation` marker to `worker_metadata`. Both completion proof fields are set together to satisfy the `chk_published_proof` schema constraint.
- `claim_next_queue_item` filters `WHERE external_media_id IS NULL`, so once anchored the row cannot be reclaimed and re-published — even if `write_attempt()` or `mark_published()` fail afterward.
- If `_anchor_media_id()` itself fails, the worker attempts a fallback to `queue_status = 'failed'` (which also excludes the row from the claim eligibility set), logs CRITICAL, and exits without scheduling a retry.
- If both anchor and fallback fail, the row may be reclaimed after the lock expires. This is logged as CRITICAL and requires immediate operator action.
- `write_attempt()` and `mark_published()` run after the anchor. Any failure in Phase 2 logs CRITICAL but cannot cause duplicate publishing — `external_media_id` is already set.
- The row is never scheduled for retry after a confirmed `media_id` — an operator must set `published_at` and `queue_status = published` manually if Phase 2 fails.

## Duplicate Prevention Rules

Required:

- Skip rows with `published_at`.
- Skip rows with `external_media_id`.
- Use atomic row claiming.
- Keep `published_at` and `external_media_id` together as completion proof.
- Do not retry after known successful publish.
- Keep attempts as audit records, not source of publishing truth.

## Logging Safety

Do:

- Log worker version.
- Log queue item ID.
- Log attempt counts.
- Log redacted error categories.
- Log container/media IDs only when safe and useful.

Do not:

- Log `SUPABASE_SERVICE_ROLE_KEY`.
- Log `IG_ACCESS_TOKEN`.
- Log bearer tokens.
- Log URLs containing sensitive query params.
- Log full Instagram request URLs with access tokens.

## Manual Run Commands

Dry-run from the repo root:

```bash
cd /Users/vasylpopovich/Projects/InstaAutoPost
INSTAGRAM_API_ENABLED=false python3 scripts/instaautopost_publisher.py
```

Dry-run from the scripts directory:

```bash
cd /Users/vasylpopovich/Projects/InstaAutoPost/scripts
INSTAGRAM_API_ENABLED=false python3 instaautopost_publisher.py
```

Live run only after explicit confirmation:

```bash
cd /Users/vasylpopovich/Projects/InstaAutoPost
INSTAGRAM_API_ENABLED=true python3 scripts/instaautopost_publisher.py
```

The required Supabase and Instagram environment variables must already be exported.

## GitHub Actions Run Behavior

Workflow:

```text
.github/workflows/instaautopost-publisher.yml
```

Current state:

- The entire `instaautopost-publisher.yml` workflow is currently manually disabled in GitHub Actions for safety. While disabled, neither the cron schedule nor `workflow_dispatch` from the UI or API is available — GitHub will not execute the workflow in either mode. Do not re-enable without explicit authorization.
- A 5-minute cron schedule (`*/5 * * * *`) is defined in the YAML. Re-enabling the workflow in GitHub Actions also re-enables this cron schedule.
- `workflow_dispatch` (optional `queue_id` input) is defined in the YAML but is unavailable while the workflow is disabled.
- Single `publish` job — always live (`INSTAGRAM_API_ENABLED=true`). No `instagram-live` environment gate.
- Workflow installs Python dependencies from `scripts/requirements.txt`.
- Workflow runs `python scripts/instaautopost_publisher.py`.

## First Real Publish Checklist

- [x] Schema drift resolved — migration 20260516002000 adds `failure_reason`, `worker_metadata`, drops `error_message`.
- [x] `failure_reason` exists and is used for queue failures.
- [x] `worker_metadata` column added to migration.
- [x] Stale `processing` recovery is fixed — claim function now reclaims rows with expired locks.
- [x] Live env vars validated before queue claim — worker exits before claiming if vars are missing.
- [x] Post-`media_id` DB failure cannot cause retry — split exception handling prevents retry after confirmed publish.
- [x] Signed URL query params are redacted in logs — `_redact_url()` strips query strings before logging.
- [x] Migration 20260516002000 exists in repo and applied during dev/local verification.
- [ ] Migration 20260516002000 confirmed applied in production Supabase instance.
- [ ] Dry-run succeeds on the intended queue row.
- [x] Workflow state documented: the entire `instaautopost-publisher.yml` workflow is manually disabled in GitHub Actions for safety; cron and `workflow_dispatch` are both unavailable while disabled.
- [ ] User explicitly confirms live publishing.
