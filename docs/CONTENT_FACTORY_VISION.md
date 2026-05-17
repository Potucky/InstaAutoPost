# InstaAutoPost Content Factory Vision

## Executive Summary

InstaAutoPost is currently an Instagram-first publishing control center. The product is built around a clean queue, a safe Python worker, a Supabase database, and a React control center UI.

The long-term goal is to evolve this into a multi-platform content factory: one application, one control center, one content library, one publishing queue, one attempt log system, and a set of platform-specific publisher adapters. Instagram is the first fully implemented publishing channel. TikTok, YouTube Shorts, and Facebook are future channels to be added as adapters, not as separate projects.

This document captures the strategic direction. It distinguishes clearly between what is implemented today, what is planned, and what should not be built yet.

The guiding principle is: finish the Instagram pipeline properly first. Make decisions that do not close the door to future platform expansion. Do not prematurely rewrite the schema, the UI, or the worker into a generic multi-platform system before the first channel is stable and safe.

---

## Core Strategy

- Build one powerful control center that can govern all publishing channels from a single interface.
- Use Instagram as the first full working channel. Make it stable, safe, and auditable before expanding.
- Keep the architecture ready for TikTok, YouTube, and Facebook without being coupled to those platforms today.
- Avoid creating separate isolated applications per platform. One app, multiple adapters.
- Avoid premature broad refactoring. Each platform addition should happen through a focused, reviewable PR.
- Use small safe PRs and Claude Code/Codex review discipline at every expansion step.
- Document every architecture decision as it is made.

---

## High-Level Architecture

The long-term architecture follows a layered content factory model:

```text
Content Library
  ↓
Publishing Queue
  ↓
Platform Adapter
  ↓
Instagram / TikTok / YouTube / Facebook API
  ↓
Attempts / Logs / Analytics
  ↓
Control Center UI
```

### Content Library

Stores video assets and metadata. Assets are platform-agnostic. One video can feed multiple publishing queue rows targeting different platforms and accounts.

### Publishing Queue

Controls what should be published, when, to which platform, and to which account. Queue rows carry status, scheduling, attempt tracking, locking, failure reasons, and completion proof. The queue is the source of truth for publishing state.

### Platform Adapter

A platform adapter is the component responsible for the actual API call to one specific platform. Each adapter knows: how to authenticate, how to upload media, how to check container status, how to publish, how to interpret errors, and how to handle rate limits. Adapters are interchangeable at the worker layer.

### External Platform APIs

Each platform exposes a different API surface. Adapters translate queue rows into platform-specific API calls. The control center and queue are never aware of platform API details.

### Attempts / Logs / Analytics

Every attempt — dry-run or live — is recorded. Attempt logs are append-only. They carry status, duration, container IDs, platform media IDs, error details (redacted), and worker version. Analytics dashboards build on top of this audit trail.

### Control Center UI

The React interface. Reads Supabase state. Shows content library, queue, calendar, attempt logs, account status, and safety center. Never calls platform APIs directly. Never stores secrets.

---

## What Is Shared Across Platforms

The following components are reusable across all future platforms. They should be built once and extended, not duplicated per platform.

- **Content Library** — video assets, captions, titles, hashtags, thumbnails, and metadata. Platform-agnostic storage.
- **Publishing Queue** — queue rows with status transitions, attempt counts, retry logic, failure reasons, and completion proof.
- **Scheduler** — `scheduled_at`, `next_retry_at`, and time-based row selection.
- **Status system** — `draft`, `scheduled`, `ready`, `processing`, `published`, `retry_scheduled`, `failed`, `cancelled`.
- **Attempt logs** — append-only audit records per queue row per attempt.
- **Retry logic** — `attempt_count`, `max_attempts`, and retry scheduling on recoverable failures.
- **Locking and stale processing recovery** — `locked_at`, `locked_by`, stale lock reclaim after timeout.
- **Dry-run mode** — explicit enablement gate for live publishing. Dry-run must always be the safe default.
- **Safety rules** — no publish without explicit confirmation, no secrets in frontend, no duplicate publish after a returned platform media ID.
- **Dashboard / Control Center** — operational health view that surfaces state across all platforms and accounts.
- **Supabase database model** — PostgreSQL as the system of record, RLS for access control, service role key server-side only.
- **GitHub Actions worker model** — CI/CD-based worker execution with manual dispatch and optional cron scheduling.
- **Documentation and audit workflow** — architecture docs, decisions log, schema reference, worker reference, and roadmap.
- **Security hardening practices** — token redaction, no frontend secrets, RLS, SQL injection protection, upload validation.

---

## What Is Platform-Specific

Each platform requires a dedicated adapter. Adapters are separate implementations, not one generic abstraction.

Planned adapters (not yet built):

- **Instagram publisher** — implemented today in `scripts/instaautopost_publisher.py`.
- **TikTok publisher** — future adapter.
- **YouTube publisher** — future adapter.
- **Facebook publisher** — future adapter.

Platform-specific differences that each adapter must handle independently:

| Dimension | Per-Platform |
| --- | --- |
| OAuth / token model | Instagram uses long-lived user tokens. TikTok uses OAuth 2.0 with refresh tokens. YouTube uses Google OAuth. Facebook uses Meta app tokens. |
| API endpoints | Each platform has its own upload, status check, and publish endpoints. |
| Media upload rules | File size limits, format requirements, duration caps, and aspect ratio rules differ per platform. |
| Scheduling support | Not all platforms support server-side scheduling. Behavior varies. |
| Privacy / visibility options | Public, friends-only, unlisted, and private modes differ per platform. |
| Status check behavior | Instagram uses container status polling. Other platforms may have different confirmation models. |
| Error handling | Error codes, retry-safe signals, and fatal error signals are platform-specific. |
| Rate limits | Publish rate limits, API call limits, and account-level throttles differ per platform. |
| Platform publish IDs | Instagram returns `media_id`. TikTok returns a publish ID. YouTube returns a video ID. Facebook returns a post ID. Completion proof fields must accommodate this. |

---

## Current Instagram-First Model

The current implementation is deliberately Instagram-first.

Current tables in repo migrations:

- `public.ig_content_library`
- `public.ig_publishing_queue`
- `public.ig_publish_attempts`

This naming convention is acceptable for the first working channel. The `ig_` prefix reflects the current Instagram-only scope.

Do not rename or refactor these tables now just for future flexibility. The current priority is to make the Instagram pipeline stable, safe, and auditable. Table migration to a platform-agnostic naming convention is a future planned task, not an immediate requirement.

The current worker at `scripts/instaautopost_publisher.py` is the only Instagram publisher. It is the reference implementation for all future adapters.

---

## Future Universal Data Model

When expanding to a second platform, a planned migration should introduce platform-agnostic table naming and a platform accounts model. This should be done as a dedicated, reviewed PR — not as a side effect of another task.

Planned future tables (not yet designed or implemented):

- `content_library` — platform-agnostic content assets.
- `publishing_queue` — platform and account aware queue rows.
- `publish_attempts` — platform-agnostic attempt audit log.
- `platform_accounts` — one row per connected account per platform.
- `platform_connections` — token storage references per account.
- `channels` — optional grouping of accounts into named publishing channels.
- `platform_settings` — per-platform configuration and defaults.

This migration should happen later, as a planned and reviewed transition, not as a rushed rewrite. The existing `ig_` tables can coexist during a transition period.

---

## Multi-Account Strategy

The long-term model must support 10, 20, or 30 accounts across multiple platforms without requiring separate worker scripts per account.

The model:

- Each connected account is represented as a row in `platform_accounts`.
- Each account has associated credentials in `platform_connections` (server-side only, never in the frontend).
- One video asset in the content library can generate multiple queue rows — one per target account and platform.
- Each queue row is independent and carries its own state, attempt count, and completion proof.

Example publishing plan for one video:

```text
Video A
  → TikTok Account 1        → scheduled 2026-06-01 09:00
  → TikTok Account 2        → scheduled 2026-06-01 10:00
  → Instagram Account 1     → scheduled 2026-06-01 11:00
  → YouTube Shorts Channel  → scheduled 2026-06-01 12:00
```

The video URL and content metadata are shared. Publishing execution is account-specific and platform-specific. The queue worker selects due rows and delegates to the correct adapter based on the `platform` field.

Advantages of this model:

- Adding a new account requires only a new `platform_accounts` row and credentials — not a new script.
- Publishing plans can be created in bulk from one content asset.
- Failure in one account's queue row does not affect other accounts.
- The control center can filter by platform and account independently.

---

## Platform Accounts / Channels Concept

Future `platform_accounts` table (conceptual, not yet designed as SQL):

| Field | Purpose |
| --- | --- |
| `id` | Primary key. |
| `platform` | Platform identifier: `instagram`, `tiktok`, `youtube`, `facebook`. |
| `account_name` | Display name for the account. |
| `external_account_id` | Platform-issued account ID. |
| `status` | Account active/inactive/suspended. |
| `token_status` | Token validity status: `valid`, `expiring`, `expired`, `unknown`. |
| `created_at` | Creation timestamp. |
| `updated_at` | Last update timestamp. |
| `metadata` | Platform-specific metadata as JSON. |

Future `platform_connections` table (conceptual, not yet designed as SQL):

| Field | Purpose |
| --- | --- |
| `id` | Primary key. |
| `platform_account_id` | FK to `platform_accounts`. |
| `token_reference` | Reference to encrypted token storage — never a raw token. |
| `expires_at` | Token expiration time. |
| `scopes` | Token scope list. |
| `metadata` | Connection metadata. |

Tokens must never be stored in plaintext in the database, exposed in the UI, or logged in any form. Token storage architecture requires a dedicated security review before implementation.

---

## Publishing Queue Future Behavior

Future queue rows should include:

| Field | Purpose |
| --- | --- |
| `content_id` | FK to content library. |
| `platform` | Target platform: `instagram`, `tiktok`, etc. |
| `platform_account_id` | FK to `platform_accounts`. |
| `scheduled_at` | Publish trigger time. |
| `queue_status` | Current state. |
| `attempt_count` | Attempts made. |
| `max_attempts` | Retry ceiling. |
| `external_publish_id` | Platform-returned media or publish ID. |
| `failure_reason` | Queue-level failure description. |
| `worker_metadata` | Diagnostics and reconciliation data. |

Worker behavior for multi-platform queues:

- Worker selects due rows safely using locking and stale processing recovery.
- Worker reads the `platform` field and routes to the correct adapter.
- Each adapter handles its own API calls, error handling, and completion proof.
- Duplicate-publish protection must be implemented per adapter, equivalent to the Instagram anchor model.
- Dry-run must remain the safe default for every adapter.

---

## Control Center UI Vision

The control center should provide one unified view across all platforms and accounts.

Future UI sections:

| Section | Purpose |
| --- | --- |
| Dashboard | Operational health across all platforms: queued, scheduled, processing, failed, published today. |
| Content Library | Manage video assets and metadata before scheduling. |
| Upload Video | Upload media to storage, generate thumbnails, create content records. |
| Publishing Queue | View and manage queue rows across platforms and accounts. |
| Calendar | Visualize scheduled and published content by day and time. |
| Logs and Attempts | Attempt audit trail. Redacted. Append-only. |
| Accounts / Channels | Manage connected platform accounts and token status. |
| Platforms | Configure platform-level settings and defaults. |
| Safety Center | Live mode readiness checks, blockers, schema status, env var status. |
| Settings | Application and operator preferences. |

Required filters for queue, logs, and calendar views:

- Platform filter (Instagram, TikTok, YouTube, Facebook, All).
- Account filter (per connected account or All).
- Status filter (scheduled, failed, published, processing, etc.).
- Date and schedule filter.
- Failed and retry filter.

Future operator actions from the UI:

- Upload video and create content records.
- Create a publishing plan: select content, select target accounts and platforms, set scheduled times.
- View queue and attempt logs.
- Retry failed posts safely (only if no completion proof exists).
- Disable or pause accounts.
- Check token status without revealing token values.
- Trigger manual dry-run from the safety center.

---

## Business Logic Principles

These principles apply to every platform, every adapter, and every future expansion.

- **Database is source of truth.** Queue state, attempt logs, completion proof, and account status live in Supabase.
- **UI reads and writes controlled state.** The UI manages content and queue records. It does not publish.
- **Workers execute publishing.** Only a backend worker with a service role key calls platform APIs.
- **Every attempt is logged.** Dry-run and live attempts are recorded as append-only audit rows.
- **Real publishing requires explicit enablement.** A manual gate must be confirmed before any live API call.
- **No random file publishing.** Publishing must start from a queue row.
- **No duplicate publishing.** Completion proof fields (`external_media_id`, `published_at` or equivalents) gate every retry and reclaim decision.
- **No secrets in frontend.** Service role keys and platform tokens never reach the browser.
- **No broad changes without review.** Each expansion should be a focused PR with documentation.
- **One safe task per PR where practical.** Small PRs reduce risk and keep history legible.

---

## Security Hardening Track

Security must be treated as a first-class requirement at every expansion step. The following items apply to the current Instagram pipeline and to every future platform addition.

### Domain and Transport

- Use a custom domain with HTTPS for the control center.
- Configure DNS correctly. Verify HTTPS certificate before production use.
- Do not accept traffic on HTTP in production.

### Supabase Access Control

- RLS (Row-Level Security) must be enabled on all tables.
- The `anon` key must be limited to safe frontend operations only.
- The `service_role` key must remain server-side only: GitHub Actions, workers, and backend scripts.
- The `service_role` key must never appear in the UI, browser console output, or frontend environment variables.
- RLS policies must be reviewed before live publishing and before each new table is introduced.

### SQL Injection Protection

- Use parameterized queries and Supabase client methods. Never concatenate user input into SQL strings.
- Review RPC functions for injection risks.

### XSS Protection

- Sanitize or escape user-controlled text before rendering: captions, titles, failure reasons, metadata, and attempt logs.
- Do not render unsanitized HTML from database content.

### CSRF and Session Considerations

- Use Supabase Auth session management. Do not implement custom session tokens.
- Review CSRF exposure if any future endpoint accepts state-changing POST requests without auth.

### Secrets Management

- Supabase `service_role` key: GitHub Actions secrets only.
- Instagram `IG_ACCESS_TOKEN`: GitHub Actions secrets only.
- TikTok, YouTube, and Facebook tokens: secrets manager or GitHub Actions secrets only, never in `.env` files committed to the repo.
- Rotate tokens on a schedule and whenever a team member leaves.

### Token Protection

- Access tokens and refresh tokens must never appear in logs, database plaintext fields, or UI output.
- The `_redact_url()` pattern in the Instagram worker (stripping signed URL query parameters before logging) must be applied consistently in every adapter.
- Token storage in the database must use references to an encrypted store, not plaintext values.

### Logging Without Secrets

- Logs must redact tokens, signed URL query parameters, and service role key values.
- Error messages stored in `error_message` fields must be reviewed for accidental secret inclusion.

### API Abuse and Rate Limits

- Workers must respect platform-specific publish rate limits.
- Workers must handle rate limit errors gracefully: back off, record the failure, and schedule retry at the appropriate time.
- Do not implement retry logic that could trigger abuse detection on any platform.

### Upload and Media Validation

- Validate uploaded media against platform format rules: file type, size, duration, aspect ratio.
- Reject malformed or oversized uploads before they enter the queue.
- Validate media URLs before passing them to platform APIs.

### Backups and Recovery

- Supabase database backups should be confirmed before production use.
- Migration rollback plans should be documented before each schema change is applied to production.
- Never edit already-applied production migrations. Add new migrations for corrections.

### Web Application Risks

- Review the OWASP Top 10 before production domain launch.
- Pay attention to: injection, broken access control, security misconfiguration, insecure design, and logging and monitoring failures.
- The safety center UI screen should surface active security and readiness blockers.

### Security Audit Checkpoint

Before live publishing on a production domain:

- Complete a security review of RLS policies.
- Confirm no secrets are accessible from the browser.
- Confirm HTTPS is enforced.
- Confirm logging does not expose tokens or signed URL parameters.
- Confirm media upload validation is in place.
- Confirm the service role key is not in any frontend config.

---

## Recommended Roadmap

### Phase 1 — Finish Instagram Pipeline (Current)

- Apply migration 20260516002000 to live Supabase.
- Run a verified dry-run against a known safe queue row.
- Confirm attempt log is written and queue row resets correctly.
- Get explicit confirmation for the first live Instagram publish.
- Complete Milestone 1 through Milestone 4 from `docs/ROADMAP.md`.

### Phase 2 — Operational Dashboard and UI

- Wire dashboard cards to real Supabase data.
- Show queue status, failure reasons, and attempt logs from live database.
- Show processing and stuck rows visibly.
- Complete content library management and publishing queue UI.
- Make the calendar show real scheduled and published items.

### Phase 3 — Account and Channel Architecture Planning

- Design the `platform_accounts` and `platform_connections` schema.
- Document the token storage and credential management model.
- Review security requirements for multi-account token handling.
- Write a dedicated architecture decision record in `docs/DECISIONS.md`.

### Phase 4 — Platform Accounts Schema Migration

- Create and apply a migration adding `platform_accounts` and `platform_connections`.
- Add account management UI to the control center.
- Add token status visibility without exposing token values.
- Add account filter to queue, calendar, and attempt log views.

### Phase 5 — TikTok as Second Publisher Adapter

- Implement `scripts/tiktok_publisher.py` as the second adapter.
- Add TikTok-specific environment variables and GitHub Actions secrets.
- Extend the publishing queue to include `platform` and `platform_account_id` fields.
- Verify dry-run safety for TikTok adapter before live use.
- Document TikTok-specific API notes in `docs/TIKTOK_API_NOTES.md`.

### Phase 6 — YouTube Shorts

- Implement YouTube Shorts adapter following the same pattern as TikTok.
- Add YouTube-specific token management and OAuth flow.
- Document YouTube Shorts API constraints and quota limits.

### Phase 7 — Facebook and Meta Pages

- Evaluate business case for Facebook publishing before implementing.
- If justified, implement Facebook adapter using Meta Graph API.
- Align with existing Instagram Meta token architecture where possible.

### Phase 8 — Full Security Hardening and Production Readiness

- Complete OWASP-style security review.
- Confirm production domain, HTTPS, DNS, and RLS posture.
- Audit logging for secret exposure.
- Confirm token rotation policy.
- Confirm backup and recovery plan.
- Complete safety center UI with all readiness checks visible.

---

## Do Not Do Yet

These actions should not be taken until the relevant phase is reached and a dedicated PR is planned.

- Do not rewrite the `ig_` table naming scheme before the Instagram pipeline is stable.
- Do not split into separate applications for Instagram, TikTok, and YouTube.
- Do not enable live publishing until dry-run, migration, token, and safety checks are all confirmed.
- Do not store service role keys, access tokens, or refresh tokens in the frontend or in plaintext database fields.
- Do not create broad refactors without a dedicated PR and review.
- Do not add multi-platform abstractions before the second platform adapter is actively being built.
- Do not add AI content generation features before safe publishing works end-to-end.
- Do not restore automated GitHub Actions cron scheduling before the worker safety blockers are resolved and the user explicitly requests it.
- Do not introduce new dependencies without justification and review.

---

## Final Summary

Instagram is the first production line. It must be finished properly: safe, stable, auditable, and fully operational from queue creation through published proof.

The long-term product is one content factory. One control center. One content library. One publishing queue. One audit log system. Multiple platform adapters — Instagram first, then TikTok, YouTube, and Facebook as the business case and architecture readiness support each expansion.

Every design decision made today should keep the door open for multi-platform growth without forcing a premature rewrite. Build the first channel strongly. Expand carefully. Document every decision. Review every change.
