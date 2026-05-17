# Roadmap

## Current State

Implemented:

- Vite/React dashboard structure.
- Supabase-backed content, queue, and attempt tables in repo migrations.
- Python publisher worker at `scripts/instaautopost_publisher.py`.
- Dry-run default controlled by `INSTAGRAM_API_ENABLED`.
- Instagram Graph API live path in worker.
- GitHub Actions workflow for manual worker execution.
- Automatic workflow schedule is currently disabled to stop failure email spam.

Partially implemented:

- Content library and publishing queue UI.
- Calendar and dashboard views.
- Attempt log visibility.
- Development RLS policies.
- Worker retry handling.

Blocked:

- First real Instagram publish.
- Production automation.
- Broad feature expansion.

## Active Safety Blockers

Fixed (worker v1.2.0 + migration 20260516002000):

1. ~~Rows can get stuck in `processing`~~ — claim function now reclaims stale `processing` rows (lock > 10 min); content fetch failure unlocks the row immediately.
2. ~~Post-`media_id` duplicate publish edge case~~ — `_anchor_media_id()` writes `external_media_id` as the very first DB write after Instagram confirms publication. `claim_next_queue_item` filters `WHERE external_media_id IS NULL`, so once anchored the row can never be reclaimed and re-published — even if all subsequent DB writes fail. Fallback: if the anchor itself fails, worker marks `queue_status = failed` (also excluded from claim eligibility) and exits without retry.
3. ~~Live env vars validated after claim~~ — worker exits before claiming if `IG_USER_ID` or `IG_ACCESS_TOKEN` are missing.
4. ~~`video_url` query params logged in plaintext~~ — `_redact_url()` strips query strings before logging.
5. ~~Schema drift~~ — migration 20260516002000 adds `failure_reason`, `worker_metadata`, and drops `error_message` from `ig_publishing_queue`.

Remaining before first real publish:

- Confirm migration 20260516002000 is applied to production Supabase (applied in dev/local verification).
- Run a dry-run against a known safe queue row and verify the attempt log.
- Confirm `claim_next_queue_item` executes cleanly under the service role.
- Get explicit user confirmation for the live publish.

Known edge case (not blocking dry-run):

- Stale `processing` rows at `max_attempts` cannot be auto-reclaimed. Operator must manually cancel or reset them.

## Immediate Next Steps

1. Confirm migration 20260516002000 is applied to production Supabase.
2. Run dry-run manually against a known safe queue item.
3. Review database state after dry-run (attempt log written, row reset to `scheduled`).
4. Only then request explicit confirmation for a live publish.

## MVP Milestones

### Milestone 1: Safe Worker Foundation

- Schema alignment complete.
- Dry-run verified.
- Stale locks recoverable.
- Duplicate publish protection after `media_id`.
- Clear first-run checklist.

### Milestone 2: Operational Dashboard

- Dashboard cards show queue health.
- Queue screen shows `failure_reason`.
- Attempt logs are readable.
- Stuck `processing` rows are visible.
- Calendar shows scheduled and published items.

### Milestone 3: Controlled First Live Publish

- User confirms live run.
- One queue item is selected and verified.
- Live mode is enabled only for the run.
- Published proof is stored.
- Attempt log is written.
- No retry is scheduled after success.

### Milestone 4: Repeatable Manual Operations

- Manual GitHub Actions run works.
- Dry-run and live run instructions are documented.
- Error triage steps are documented.
- UI surfaces enough state for operations.

## Post-MVP Milestones

- Re-enable scheduled publishing with a deliberate cron.
- Add workflow concurrency controls if needed.
- Add account connection status screen.
- Add safety center screen.
- Add media upload to Supabase Storage.
- Add thumbnail generation.
- Add analytics dashboard.
- Add bulk scheduling.
- Add calendar drag-and-drop rescheduling.
- Add token rotation support.

## Future Expansion

- AI caption and hashtag assistance.
- AI content factory pipeline.
- Multi-account Instagram support.
- Multi-platform support.
- Team review and approval workflows.
- Performance analytics and recommendation engine.

## What Can Wait

- Advanced analytics.
- Team collaboration.
- Multi-platform publishing.
- Automated content generation.
- Complex calendar interactions.
- Token refresh automation.
- Slack or webhook notifications.

## What Should Not Be Built Yet

- Direct browser-based Instagram publishing.
- Broad multi-platform abstractions.
- AI content factory features before safe publishing works.
- Complex campaign management.
- Production cron automation before worker blockers are fixed.
- UI controls that imply live publishing is safe before it is.
