# InstaAutoPost

InstaAutoPost is a standalone Instagram autoposting control center backed by Supabase, a queue-based publishing worker, GitHub Actions automation, and the Instagram Graph API.

It is not QA Automation, not QA Content Automation, and not an old Instagram project.

## Start Here

- `CLAUDE.md` - rules for Claude Code/Codex and safety-sensitive work.
- `docs/PRODUCT_BLUEPRINT.md` - product vision and MVP scope.
- `docs/ARCHITECTURE.md` - system architecture and data flow.
- `docs/CONTROL_CENTER_REQUIREMENTS.md` - dashboard and UI requirements.
- `docs/SUPABASE_SCHEMA.md` - schema contract and drift warnings.
- `docs/PUBLISHING_WORKER.md` - worker behavior, dry-run/live mode, and first-run checklist.
- `docs/INSTAGRAM_API_NOTES.md` - Instagram API safety notes.
- `docs/ROADMAP.md` - active blockers and next milestones.
- `docs/DECISIONS.md` - architecture decision log.

`docs/INSTAAUTOPOST_FACTORY.md` is an earlier architecture reference. The files above are the active source-of-truth documentation set.

## Architecture

| Layer | Component | Responsibility |
| --- | --- | --- |
| Frontend | Vite + React + TypeScript | Manage content, queue, calendar, and logs. Never publishes directly. |
| Database | Supabase PostgreSQL | Source of truth for content, queue state, attempts, locks, and completion proof. |
| Worker | `scripts/instaautopost_publisher.py` | Owns Instagram Graph API publishing. Dry-run by default. |
| Automation | `.github/workflows/instaautopost-publisher.yml` | Manual worker execution. Automatic schedule is currently disabled. |
| External API | Instagram Graph API | Receives live publish requests only when explicitly enabled. |

## Project Structure

```text
InstaAutoPost/
  CLAUDE.md
  README.md
  docs/
    ARCHITECTURE.md
    CONTROL_CENTER_REQUIREMENTS.md
    DECISIONS.md
    INSTAGRAM_API_NOTES.md
    PRODUCT_BLUEPRINT.md
    PUBLISHING_WORKER.md
    ROADMAP.md
    SUPABASE_SCHEMA.md
  scripts/
    instaautopost_publisher.py
    requirements.txt
  supabase/
    migrations/
    policies/
  .github/
    workflows/
      instaautopost-publisher.yml
  ui/
```

## Current Status

Implemented:

- React control center structure.
- Supabase schema migrations and dev RLS policies.
- Python publisher worker.
- GitHub Actions workflow with manual dispatch.
- Dry-run default controlled by `INSTAGRAM_API_ENABLED`.
- Stale `processing` row recovery (migration 20260516002000).
- Post-`media_id` atomic anchor preventing duplicate publishing.
- Live env var validation before queue claim.
- Signed URL and token log redaction.
- Queue failure field is `failure_reason` (UI and worker aligned).

Blocked before real Instagram publishing:

- Migration 20260516002000 not yet applied to live Supabase.
- Dry-run not yet confirmed on an intended queue row.
- User has not confirmed a live publishing run.

## Running The UI

```bash
cd ui
npm install
npm run dev
```

Required browser env vars:

- `VITE_SUPABASE_URL`
- `VITE_SUPABASE_ANON_KEY`

## Worker Dry-Run

Dry-run does not call Instagram, but it does connect to Supabase and write/update queue and attempt records.

```bash
cd /Users/vasylpopovich/Projects/InstaAutoPost
INSTAGRAM_API_ENABLED=false python3 scripts/instaautopost_publisher.py
```

Required worker env vars:

- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`

## Live Publishing

Do not run live publishing until the safety blockers in `docs/ROADMAP.md` and `docs/PUBLISHING_WORKER.md` are fixed and the user explicitly confirms a live run.

Live mode is gated by:

```text
INSTAGRAM_API_ENABLED=true
```

Live-only env vars:

- `IG_USER_ID`
- `IG_ACCESS_TOKEN`

## Automation

The GitHub Actions workflow keeps manual `workflow_dispatch`.

Automatic cron scheduling is currently commented out in `.github/workflows/instaautopost-publisher.yml` to stop failure email spam. Restore it only after safety blockers are resolved and the user explicitly asks.
