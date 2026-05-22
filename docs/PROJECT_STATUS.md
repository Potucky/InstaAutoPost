# PROJECT_STATUS.md

Current known status of the InstaAutoPost project. Updated from read-only local inspection only. If a field cannot be determined safely, it is marked UNKNOWN.

---

## Status Snapshot

```
Project:               InstaAutoPost
Current branch:        agent/iap-001-orchestrator-bootstrap
Last updated:          2026-05-22 (IAP-002 queued)

Production status:
  Publishing:          DISABLED — scheduled cron commented out in workflow
  Worker mode:         Dry-run (INSTAGRAM_API_ENABLED not confirmed set to true)
  UI:                  UNKNOWN — not inspected in this snapshot

GitHub Actions status:
  Workflow file:       .github/workflows/instaautopost-publisher.yml (present)
  Scheduled trigger:  DISABLED (temporarily disabled per recent commits)
  Manual dispatch:    UNKNOWN — file not read in this snapshot

Supabase status:
  Live schema:         UNKNOWN — no live DB connection made
  Migration drift:     UNKNOWN — not verified against live Supabase
  Blocker:             Migration drift must be verified before any real publish run

Instagram API status:
  Live publishing:     DISABLED
  INSTAGRAM_API_ENABLED: not confirmed true in any current run
  Access token:        NOT inspected (safety rule: do not print tokens)

Known blockers:
  1. Migration drift between repo and live Supabase not verified — blocks real publishing.
  2. Scheduled publishing is disabled — re-enable requires explicit user approval.

Agent workflow:
  IAP-001:             DONE — Orchestrator bootstrap complete, Codex PASS received.
  IAP-002:             TODO — Read-only audit of current InstaAutoPost pipeline.
  Next task:           IAP-002
  Queue file:          docs/AGENT_TASK_QUEUE.md
  Run reports:         docs/AGENT_RUN_REPORT.md
  Review rules:        docs/AGENT_REVIEW_RULES.md
  Security rules:      docs/SECURITY_RULES.md
```

---

## Update Instructions

When updating this file:

- Run only safe read-only commands (`pwd`, `git status`, `git branch`, `find`, `ls`).
- Do not connect to Supabase, Instagram, or any external service to update this file.
- If a field cannot be determined from local inspection, write `UNKNOWN`.
- Record the date in `Last updated`.
- Do not commit this file automatically — commit only when the user asks.
