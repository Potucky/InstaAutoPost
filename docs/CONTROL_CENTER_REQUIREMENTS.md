# Control Center Requirements

## Purpose

The InstaAutoPost control center is an operational dashboard for Instagram autoposting. It should help the user understand content, schedule, queue health, publishing safety, and failure history without needing to inspect raw database rows.

## Interface Principles

- Clear, modern, work-focused UI.
- Dense enough for operations, not a marketing landing page.
- Status-first design: every row should show state, timing, attempts, and errors clearly.
- Mobile-friendly layouts for review and status checks.
- No secrets in the browser.
- No direct Instagram publishing from the UI.
- Live publishing actions must require explicit confirmation.
- Empty states should tell the operator what is missing and what action is available.
- Error states should be actionable, not vague.

## Dashboard Cards

Required cards:

- Total content assets.
- Scheduled or queued items.
- Items due now.
- Processing items.
- Failed items.
- Published today.
- Recent dry-run attempts.
- Recent live publish attempts.
- Safety status: dry-run, live disabled, live enabled, blocked.

Card behavior:

- Cards should link to the relevant detailed view.
- Counts should be based on Supabase state.
- Failed and processing states should be visually prominent.

## Content Library Screen

Purpose:

- Manage reusable Instagram content assets before scheduling.

Required fields:

- Title.
- Caption.
- Video URL.
- Thumbnail URL when available.
- Hashtags.
- Content status.
- Media type.
- Duration when available.
- File size when available.

Required actions:

- Create content.
- Edit metadata.
- Approve content.
- Archive content.
- Add approved content to queue.

States:

- Draft.
- Approved.
- Archived.

Empty state:

- Show that no content exists and offer the primary add-content action.

## Publishing Queue Screen

Purpose:

- Manage scheduled publishing intents.

Required display:

- Content title.
- Queue status.
- Scheduled time.
- Published time.
- Attempt count and max attempts.
- Failure reason.
- Lock status when processing.
- External media ID when published.

Required actions:

- Schedule draft queue item.
- Mark item ready when that state is used.
- Cancel eligible items.
- Retry failed items when attempts remain.
- Open linked attempt history.

Safety requirements:

- Do not allow retry for rows that already have `published_at` or `external_media_id`.
- Show stuck `processing` rows.
- Show `failure_reason` from `ig_publishing_queue`, not `error_message`.

## Calendar And Scheduler Screen

Purpose:

- Visualize publishing plans by day and time.

Required views:

- Month view.
- Week or agenda view.
- Day detail view.

Required behavior:

- Show scheduled, retry scheduled, processing, published, failed, and cancelled states.
- Make failed and stuck items visible.
- Support rescheduling in a future iteration.
- Avoid hiding queue rows without scheduled times.

## Attempt Logs Screen

Purpose:

- Provide an audit trail of worker behavior.

Required display:

- Attempt time.
- Queue item.
- Content title.
- Attempt number.
- Status: `dry_run`, `success`, or `failed`.
- Duration.
- Container ID when present.
- Media ID when present.
- Error message when safe.
- Worker version.

Required safety:

- Never show tokens.
- Never show signed URL query parameters.
- Keep attempts append-only.

## Account Connection Screen

Purpose:

- Show whether live Instagram publishing can be attempted.

Planned display:

- Instagram account ID configured: yes/no.
- Access token configured: yes/no.
- Live publishing enabled: yes/no.
- Last dry-run result.
- Last live attempt result.
- Token age or rotation status when available.

Do not display secret values.

## Safety Center Screen

Purpose:

- Make first-run and production readiness obvious.

Required checks:

- `INSTAGRAM_API_ENABLED` status.
- Required live env vars configured.
- Workflow schedule enabled or disabled.
- Stuck `processing` row count.
- Queue rows with completion proof.
- Failed attempt count.
- Schema drift status.
- Active blockers from `docs/ROADMAP.md`.

Required actions:

- Run dry-run manually outside the UI.
- Link to worker instructions.
- Confirm live publish readiness checklist.

## Status Labels And Colors

Conceptual labels:

- Draft: neutral.
- Scheduled: blue.
- Ready: indigo.
- Processing: amber.
- Published: green.
- Retry scheduled: orange.
- Failed: red.
- Cancelled: gray.
- Dry-run attempt: muted blue or gray.

Colors should aid scanning but must not be the only signal.

## Confirmation Requirements

Before any future UI action can trigger or request live publishing:

- Show the target account.
- Show the content title and scheduled item.
- Show whether live mode is enabled.
- Confirm that dry-run was recently successful.
- Require explicit user confirmation.
- Do not expose tokens or signed URL query params.

The current UI should remain queue-management only. Live publishing is controlled by the worker and environment gate.

