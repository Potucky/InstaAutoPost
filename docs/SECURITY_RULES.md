# SECURITY_RULES.md

Non-negotiable security rules for all agents, automation, and humans working in InstaAutoPost.

These rules apply at all times. They are not overridden by task scope, urgency, or convenience.

---

## Secrets and Credentials

- **Never print secrets or tokens.** Do not output `IG_ACCESS_TOKEN`, `SUPABASE_SERVICE_ROLE_KEY`, refresh tokens, client secrets, signed URL query parameters, or any value derived from them — in logs, in terminal output, in documentation, or in code comments.
- **Never commit secrets.** No credentials, API keys, tokens, or `.env` files with real values may be committed to the repository.
- **Keep API credentials server-side only.** The UI must not hold or transmit Instagram Graph API credentials. Worker credentials must not appear in client-side bundles.
- **Logs must not include** access tokens, refresh tokens, service role keys, client secrets, or full API responses that contain any of the above. Redact before logging.

---

## Publishing Safety

- **Never publish to Instagram or TikTok without explicit user approval.** Explicit means the user typed the specific instruction in the current session. A previous session's approval does not carry over.
- **Never run the publisher (`scripts/instaautopost_publisher.py`) with `INSTAGRAM_API_ENABLED=true`** unless the user explicitly confirms that live action in the current session.
- **Dry-run is the default.** When `INSTAGRAM_API_ENABLED` is unset or `false`, the worker must remain safe and must not make real API calls.
- **All production publishing must require explicit manual confirmation** from the user before any queue row is claimed for live publishing.

---

## Automation and Scheduling

- **Never enable cron-based publishing without explicit user approval.** The scheduled trigger in `.github/workflows/instaautopost-publisher.yml` must remain disabled unless the user explicitly asks to restore it.
- **Never merge to main automatically.** No agent or workflow may merge a branch to `main` without user confirmation.
- **Never deploy production automatically.** No agent or workflow may trigger a production deployment without user confirmation.

---

## Database and Schema

- **Never apply destructive SQL without explicit user approval.** DROP TABLE, TRUNCATE, DELETE without WHERE, or column removal must not run without confirmation.
- **Never apply Supabase migrations without explicit user approval.** Migrations must be reviewed and confirmed before running against any live Supabase project.
- **Treat migration drift as a blocker.** If the repo migration state does not match the live Supabase schema, do not proceed with any real publishing run.

---

## Duplicate Publish Prevention

- **If Instagram returns a real `media_id`, subsequent database or logging failures must not schedule a retry** that could cause a duplicate publish. Idempotency at the publish step is required.
- **The worker must not publish rows that already have `published_at` or `external_media_id` set.**

---

## Code Safety

- **No command injection.** Shell commands constructed from external or user-supplied input must be parameterized or sanitized.
- **No SQL injection.** All database queries must use parameterized queries or the Supabase client's safe query methods.
- **No XSS.** UI output must escape user-controlled content before rendering.
- **No open redirects.** The UI must not redirect to externally supplied URLs without validation.

---

## Scope

- **Agents must work only within the declared task scope.** Files outside `Allowed files` must not be read (beyond inspection) or written.
- **Do not touch other projects.** QA Content Automation, TikTok projects, CreatorFlow, and any other repository outside `/Users/vasylpopovich/Projects/InstaAutoPost` are off-limits.
