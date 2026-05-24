# Roadmap

## Current State

Implemented:

- Vite/React dashboard structure.
- Supabase-backed content, queue, and attempt tables in repo migrations.
- Python publisher worker at `scripts/instaautopost_publisher.py`.
- Dry-run default controlled by `INSTAGRAM_API_ENABLED`.
- Instagram Graph API live path in worker.
- GitHub Actions workflow for manual worker execution.
- Publisher workflow has a 5-minute cron defined in YAML; the entire `instaautopost-publisher.yml` workflow is currently manually disabled in GitHub Actions for safety. While disabled, neither the cron nor `workflow_dispatch` is available. Re-enabling the workflow resumes the cron.

Partially implemented:

- Content library and publishing queue UI.
- Calendar and dashboard views.
- Attempt log visibility.
- Worker retry handling.

Implemented (Task 4.1 + 4.2):

- Public signup disabled in UI by default.
- Admin-only RLS posture: `public.instaautopost_admins` allowlist table, `public.is_instaautopost_admin()` helper, admin-only policies on all four core tables and on storage write operations (migration `20260523001000_harden_admin_only_rls.sql`).
- First admin UUID must be inserted manually via SQL before the UI is usable in production (see `docs/SUPABASE_SCHEMA.md` — Admin Allowlist).

Implemented (Task 8):

- Publisher workflow concurrency: `group: instaautopost-publisher`, `cancel-in-progress: false`. Overlapping runs are prevented; one pending run may wait.

Implemented (Publisher simplification):

- Removed two-job workflow split (`publish_dry_run` / `publish_live`) — replaced with a single `publish` job that always runs live (`INSTAGRAM_API_ENABLED=true`).
- Removed `live_mode` and `live_confirmation` workflow inputs. Only `queue_id` remains as an optional dispatch input.
- Removed `INSTAAUTOPOST_LIVE_CONFIRMATION` env var and the corresponding script guard.
- Removed `instagram-live` environment gate requirement from the production workflow.
- Edge function (`trigger-publish`) no longer requires or forwards `live_confirmation` — dispatches only `queue_id`.
- UI "Publish Now" modal no longer references `PUBLISH LIVE`. Checkbox confirmation UX is kept.
- Dry-run support is preserved for local/developer use via `INSTAGRAM_API_ENABLED=false` when running the script directly.

Implemented (Task 9):

- Script separation: production worker stays at `scripts/instaautopost_publisher.py`; manual/admin DB utilities moved to `scripts/admin/`; local/test/diagnostic utilities moved to `scripts/local/`.
- `scripts/README.md` added with a safety matrix covering who calls each script, whether it can mutate Supabase, and the rule that the GitHub Actions workflow must call only `scripts/instaautopost_publisher.py`.
- Production automation must not invoke scripts in `scripts/admin/` or `scripts/local/`.

Implemented (Task 10):

- Upload validation: `UploadVideo.tsx` now rejects empty files, non-MP4 files, and files over 45 MB with a user-facing error before any upload attempt. Accepted formats: `video/mp4` or `.mp4` extension fallback when `file.type` is empty.
- Anonymous path fallback removed: upload requires an authenticated user (`user.id`). Storage path uses `crypto.randomUUID()` with a UUID-compatible fallback.
- Best-effort orphan cleanup: on DB insert failure and on Clear/Cancel, the UI checks whether the uploaded object is referenced in `ig_content_library` before attempting removal. Cleanup errors do not mask the original DB error.
- Report-only orphan detection: `scripts/admin/report_orphan_storage_files.py` lists Storage objects in `instaautopost-media` that are older than 24h (configurable) and not referenced by any content library row. No files are deleted; report only.
- Cleanup deletion is not implemented. Any destructive orphan cleanup must be a future explicit reviewed operation.

Blocked:

- First real Instagram publish.
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
- Run a manual workflow dispatch against a known safe queue item and verify the attempt log.
- Confirm `claim_next_queue_item` executes cleanly under the service role.

Known edge case (not blocking dry-run):

- Stale `processing` rows at `max_attempts` cannot be auto-reclaimed. Operator must manually cancel or reset them.

## Immediate Next Steps

1. Confirm migration 20260516002000 is applied to production Supabase.
2. Run a manual workflow dispatch against a known safe queue item.
3. Verify the attempt log and queue state after the run.

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
- Production workflow sets `INSTAGRAM_API_ENABLED=true`; safety comes from queue eligibility, concurrency controls, and duplicate publish protection.
- Published proof is stored.
- Attempt log is written.
- No retry is scheduled after success.

### Milestone 4: Repeatable Manual Operations

- Manual GitHub Actions run works.
- Dry-run and live run instructions are documented.
- Error triage steps are documented.
- UI surfaces enough state for operations.

## Post-MVP Milestones

- Confirm scheduled publishing cron cadence is appropriate for production load.
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
- Expanding cron automation scope before the first real publish is verified.
- UI controls that imply live publishing is safe before it is.
