# CLAUDE.md

## Project Identity

InstaAutoPost is a standalone Instagram autoposting control center.

This project is not QA Automation, not QA Content Automation, and not an old Instagram automation project. Do not copy patterns, names, files, assumptions, or branding from other projects unless the user explicitly asks for a comparison.

Allowed project path:

```text
/Users/vasylpopovich/Projects/InstaAutoPost
```

Work only inside this repository unless the user explicitly gives another path for a specific task.

## Source Of Truth

Read these docs before broad coding work:

- `README.md` - entry point and doc map.
- `docs/PRODUCT_BLUEPRINT.md` - product intent and scope.
- `docs/ARCHITECTURE.md` - system boundaries and data flow.
- `docs/CONTROL_CENTER_REQUIREMENTS.md` - UI and dashboard requirements.
- `docs/SUPABASE_SCHEMA.md` - database schema rules and drift warnings.
- `docs/PUBLISHING_WORKER.md` - worker behavior and safety rules.
- `docs/INSTAGRAM_API_NOTES.md` - Instagram API safety notes.
- `docs/ROADMAP.md` - current status and next work.
- `docs/DECISIONS.md` - architecture decision log.

`docs/INSTAAUTOPOST_FACTORY.md` is an earlier architecture reference. Treat the files above as the active source-of-truth documentation set.

## Non-Negotiable Safety Rules

- Do not publish to Instagram unless the user explicitly asks for a real publish run.
- Never run the worker with `INSTAGRAM_API_ENABLED=true` unless the user explicitly confirms that exact live action.
- Preserve dry-run safety. Dry-run is the default and must remain safe when `INSTAGRAM_API_ENABLED` is unset or false.
- Do not print secrets, service role keys, access tokens, refresh tokens, signed URLs, or full URLs with sensitive query strings.
- Do not log `IG_ACCESS_TOKEN`, `SUPABASE_SERVICE_ROLE_KEY`, or values derived from them.
- Do not change environment variable names without explicit instruction.
- Do not commit automatically unless the user asks.
- Do not modify unrelated files.
- Do not inspect or touch old QA Content Automation projects, TikTok projects, CreatorFlow projects, or other repos.

## Coding Rules

- Prefer small, focused changes that match the existing Vite/React, Supabase, Python, and GitHub Actions structure.
- Read implementation and docs before editing.
- Keep UI code in `ui/`.
- Keep worker code in `scripts/`.
- Keep Supabase migrations in `supabase/migrations/`.
- Keep GitHub Actions workflows in `.github/workflows/`.
- Do not introduce new dependencies unless the user asks and the dependency is justified.
- For documentation-only tasks, do not change Python, SQL, workflow behavior, app behavior, dependencies, or secrets references.

## Schema Rules

- `public.ig_publishing_queue` is the queue control table.
- The live queue failure field is `failure_reason`.
- Do not use `error_message` on `public.ig_publishing_queue`.
- `error_message` may be used only on `public.ig_publish_attempts` if the current attempts schema supports it.
- Live schema facts provided for `public.ig_publishing_queue` include:
  - `failure_reason`
  - `worker_metadata`
  - `queue_status`
  - `published_at`
  - `external_media_id`
  - `updated_at`
  - `locked_at`
  - `locked_by`
  - `attempt_count`
  - `max_attempts`
  - `scheduled_at`
  - `next_retry_at`
- Treat migration drift as a blocker before real publishing. The repo migration must match live Supabase before production runs.

## Worker Rules

- Main worker: `scripts/instaautopost_publisher.py`.
- The worker must process queue rows only through Supabase state.
- The UI must not call the Instagram Graph API.
- The worker must not publish rows that already have `published_at` or `external_media_id`.
- Live environment variables should be validated before claiming a queue row.
- If Instagram returns a real `media_id`, later database or logging failures must not schedule a retry that could duplicate publish.
- Claimed rows must not remain stuck in `processing` after pre-publish failures.
- Logs must redact tokens and signed URL query parameters.

## GitHub Actions Rules

- Publisher workflow: `.github/workflows/instaautopost-publisher.yml`.
- Keep `workflow_dispatch` available for manual runs when possible.
- Do not re-enable scheduled publishing unless the user explicitly asks.
- If scheduled publishing is restored, make the cron intent clear in a YAML comment.
- Do not remove secrets references unless the user asks.

## Documentation Rules

Update docs when:

- Queue schema or status transitions change.
- Worker dry-run/live behavior changes.
- GitHub Actions trigger behavior changes.
- Environment variables change.
- UI requirements or product scope changes.
- A safety blocker is fixed or a new blocker is discovered.

When adding implementation details to docs, clearly separate:

- Implemented
- Planned
- Blocked
- Future

## Final Response Requirements

For code or doc changes, final responses should include:

- Changed file paths.
- A short summary of what changed.
- Any assumptions made.
- Verification performed.
- Remaining blockers, especially anything required before real Instagram publishing.

