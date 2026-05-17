# InstaAutoPost Product Blueprint

## Purpose

InstaAutoPost is a standalone Instagram autoposting control center. It gives an operator a central dashboard for managing content, scheduling posts, tracking publishing attempts, and running safe Instagram Graph API publishing through a backend worker.

The product is inspired by product principles from mature social media management tools such as Hootsuite, Later, Buffer, Sprout Social, SocialPilot, Planable, Sendible, Agorapulse, Zoho Social, Metricool, and similar platforms. It does not copy competitor UI or proprietary workflows. It extracts durable principles: clear queues, visual schedules, transparent status, safe publishing controls, and strong operational visibility.

## Target User

Primary user:

- A content operator or solo builder managing Instagram Reels publishing.
- Needs a dashboard that shows what is ready, scheduled, processing, failed, and published.
- Needs confidence that no duplicate publishing will happen.
- Needs a simple path from content asset to scheduled post to published proof.

Secondary future users:

- Small teams reviewing content before scheduling.
- Operators managing multiple Instagram accounts.
- Creators using an AI-assisted content factory before scheduling.
- Multi-platform publishing operators.

## Product Principles

- Central dashboard/control center: one place to understand publishing health.
- Visual publishing calendar: scheduled content should be easy to scan by day and time.
- Queue-based scheduling: publishing is driven by database state, not ad-hoc files or manual scripts.
- Safe publishing workflow: dry-run is default; live mode must be explicit.
- Content library first: assets and metadata are managed before they enter the queue.
- Account connection visibility: operators should know whether publishing credentials are ready.
- Attempt logs: every dry run and publish attempt should leave an audit trail.
- Retry/error visibility: failures should be readable and actionable.
- Analytics-ready structure: published records and attempt logs should support later reporting.
- Clean modern UI: compact, legible, operational, and focused on repeat use.
- Scalable architecture: UI, database, worker, scheduler, and external APIs have clear boundaries.
- Strong duplicate protection: completion proof and retry rules are first-class product requirements.
- Strong AI-agent documentation: future Claude Code/Codex work should start from clear docs.

## Core Workflows

Implemented or partially implemented:

- Create or manage content records in `ig_content_library`.
- Add approved content to `ig_publishing_queue`.
- Schedule queue items by setting `scheduled_at` and `queue_status`.
- Run a Python publisher worker manually or through GitHub Actions.
- Write publish attempts to `ig_publish_attempts`.
- View queue and attempt status in the dashboard.

Planned:

- Clear account connection status screen.
- Safety center for live mode readiness.
- Stronger recovery tools for stuck queue rows.
- Better calendar and bulk scheduling workflows.
- Content upload and storage management.
- Analytics dashboards after publishing history exists.

Blocked before first real publish:

- Worker safety fixes listed in `docs/ROADMAP.md`.
- Repo schema alignment with live Supabase schema.
- Confirmation that live environment variables are configured and redacted safely.

## Core Modules

### Dashboard

Shows operational health: queued, scheduled, processing, failed, published today, and recent attempts.

### Content Library

Stores video assets and metadata such as title, caption, URL, hashtags, status, duration, and thumbnail.

### Publishing Queue

Controls what should be published and when. Queue rows carry status, scheduled time, attempt count, lock fields, failure reason, and completion proof.

### Calendar

Visualizes scheduled and published items across time. The calendar should support scanning, rescheduling, and future drag-and-drop workflows.

### Attempts And Logs

Shows every dry-run and live attempt with status, duration, container ID, media ID, and error details where safe.

### Account Connection

Future screen for Instagram account readiness, token status, and publishing capability checks without revealing secrets.

### Safety Center

Future screen for live publish readiness: dry-run status, environment variables present, queue health, schema alignment, and active blockers.

## MVP Scope

MVP means an operator can:

- Log into the dashboard.
- Add content metadata.
- Queue and schedule content.
- See queue state and attempts.
- Run the worker in dry-run mode safely.
- Run the worker in live mode only after explicit enablement.
- Understand failures without reading raw database rows.

MVP also requires:

- No duplicate publish after a returned `media_id`.
- No permanently stuck `processing` rows after common worker failures.
- Schema and code agree on queue fields.
- GitHub Actions schedule behavior is intentional and documented.

## Not In Scope For Now

- Multi-platform publishing.
- Automated AI content generation.
- Team approval workflows.
- Advanced social listening.
- Automated Instagram token refresh.
- Revenue analytics.
- Complex campaign management.
- Editing video files inside the app.
- Replacing mature social media management suites.

## Future Expansion

Future directions:

- AI content factory that generates captions, hashtags, and publish plans.
- Multi-account Instagram support.
- Multi-platform expansion for TikTok, YouTube Shorts, Facebook, LinkedIn, and X.
- Content performance analytics.
- Approval workflows and comments.
- Brand voice profiles and asset governance.
- Calendar drag-and-drop, bulk actions, and queue optimization.

## Professional-Grade Definition

For this product, professional-grade means:

- Clear operational state at all times.
- Explicit live publishing controls.
- Strong protection against duplicate publishes.
- Recoverable failure states.
- Minimal secret exposure.
- Durable audit trail.
- Schema and code drift detection.
- Documentation that lets future AI agents make safe changes.
- Interfaces designed for repeated operational use, not marketing decoration.

