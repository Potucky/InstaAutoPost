# Architecture Decision Log

## 2026-05-16: Project Name Is InstaAutoPost

Decision:

- The project is named InstaAutoPost.
- Branding should remain InstaAutoPost unless the user explicitly requests a rename.

Rationale:

- This is a standalone Instagram autoposting control center.

## 2026-05-16: Separate From Old QA Content Automation

Decision:

- InstaAutoPost is separate from old QA Content Automation and any other prior automation project.
- Do not reuse old project branding, table assumptions, workflow assumptions, or product copy.

Rationale:

- Avoid cross-project drift and accidental changes to unrelated systems.

## 2026-05-16: Use Supabase Queue As Source Of Publishing State

Decision:

- Publishing is driven by Supabase queue rows.
- The worker processes `public.ig_publishing_queue`.
- Attempts are recorded in `public.ig_publish_attempts`.

Rationale:

- Database state is inspectable, recoverable, and suitable for a dashboard/control center.

## 2026-05-16: Use Dry-Run Gate

Decision:

- Dry-run is the default.
- Live publishing requires `INSTAGRAM_API_ENABLED=true`.

Rationale:

- Prevent accidental Instagram publishing during development and audits.

## 2026-05-16: Use `failure_reason` Instead Of Queue `error_message`

Decision:

- Queue-level failures belong in `ig_publishing_queue.failure_reason`.
- Do not use `ig_publishing_queue.error_message`.
- Attempt-level errors may use `ig_publish_attempts.error_message` if the attempts schema supports it.

Rationale:

- The live queue schema uses `failure_reason`.
- Prior failures occurred when code attempted to update a non-existent queue `error_message` column.

## 2026-05-16: Do Not Retry After `media_id` Without Reconciliation

Decision:

- Once Instagram returns a real `media_id`, later local failures must not cause normal retry scheduling.
- The row should preserve completion proof or enter a manual reconciliation path.

Rationale:

- Retrying after a successful Instagram publish can duplicate posts.

## 2026-05-16: Documentation-First Before Broad Feature Work

Decision:

- Create source-of-truth docs before broad dashboard or platform expansion.
- Keep implementation, schema, worker behavior, and roadmap aligned with docs.

Rationale:

- This project is safety-sensitive. Future AI agents need clear project boundaries and publishing rules.

## 2026-05-16: Automatic Workflow Schedule Temporarily Disabled

Decision:

- The GitHub Actions publisher workflow keeps manual `workflow_dispatch`.
- The cron schedule is commented out.

Rationale:

- Stop failure email spam while worker safety and schema issues are resolved.

