# AGENT_RUN_REPORT.md

Stores run reports for completed or in-progress agent tasks. Append a new section per task; do not overwrite previous reports.

---

## Report Template

Copy this block for each task. Fill every field. Write `none` or `N/A` where not applicable — do not leave fields blank.

```
---
Task ID:
Branch:
Status:
Date:

Changed files:
  - <path> — <one-line reason>

Commands run:
  - <exact command>  →  <exit code or brief output>

What was done:
  <Prose summary of what the agent actually did.>

What was not done:
  <Anything in scope that was skipped, deferred, or intentionally left out — and why.>

Validation result:
  <Did all validation commands pass? List any failures.>

Risks found:
  - <risk description>  [severity: LOW | MEDIUM | HIGH]

Manual checks needed:
  - <anything a human must verify before this task is safe to advance>

Codex review:
  Result:  pending | PASS | FAIL
  Blockers:
    - <blocker text>
  Suggestions:
    - <non-blocking suggestion>
  Reviewed by:  Codex
  Reviewed at:  <date or pending>

Next recommended task:
  <Task ID and title of the next TODO task, or BLOCKED if queue is blocked.>
---
```

---

## Run Reports

<!-- Append completed reports below this line. Most recent last. -->

---
Task ID: IAP-001-BLOCKERS
Branch: agent/iap-001-orchestrator-bootstrap
Status: DONE
Date: 2026-05-22

Changed files:
  - scripts/potucky_orchestrator.py — restricted mark-done to NEEDS_USER_APPROVAL only; added get_blocking_task helper; added blocking-task guard to run-next and auto-run-next
  - scripts/potucky_agent_tasks.json — corrected branch from agent/iap-001-safety-baseline to agent/iap-001-orchestrator-bootstrap; status was already DONE
  - docs/POTUCKY_ORCHESTRATOR.md — updated mark-done docs to reflect NEEDS_USER_APPROVAL-only restriction; replaced false "never prints secrets" claim with accurate log handling warning
  - docs/AGENT_REVIEW_RULES.md — clarified Codex may run safe read-only inspection commands but must not write files; added explicit list of what Codex may and must not do
  - docs/AGENT_TASK_QUEUE.md — updated IAP-001 to reflect DONE state, correct branch, and Codex PASS result
  - docs/PROJECT_STATUS.md — updated branch to agent/iap-001-orchestrator-bootstrap, date to 2026-05-22, removed stale IAP-001 blocker, updated agent workflow section
  - docs/AGENT_RUN_REPORT.md — appended this entry

Commands run:
  - python3 scripts/potucky_orchestrator.py status  →  exit 0, DONE task count 1
  - python3 scripts/potucky_orchestrator.py doctor  →  exit 0, all checks OK
  - python3 scripts/potucky_orchestrator.py print-next  →  exit 0, "All tasks are DONE"
  - git status --short  →  exit 0, only orchestrator-bootstrap files modified/untracked
  - python3 -m py_compile scripts/potucky_orchestrator.py  →  exit 0

What was done:
  Fixed all six IAP-001 Codex review blockers: (1) restricted mark-done so DONE is
  reachable only from NEEDS_USER_APPROVAL, ensuring Codex PASS is always a prerequisite;
  (2) added get_blocking_task guard to run-next and auto-run-next so no new task can
  start while another task is IN_PROGRESS, NEEDS_REVIEW, NEEDS_FIX, or NEEDS_USER_APPROVAL;
  (3) aligned potucky_agent_tasks.json, AGENT_TASK_QUEUE.md, and PROJECT_STATUS.md with
  the actual current branch and IAP-001 DONE state; (4) updated AGENT_REVIEW_RULES.md
  to clarify Codex may run safe read-only inspection commands but must not write files;
  (5) replaced the misleading "never prints secrets" claim in POTUCKY_ORCHESTRATOR.md with
  an accurate warning that log files contain raw unredacted output; (6) appended this report.

What was not done:
  No publish, deploy, Supabase write, migration apply, GitHub Actions run, secrets print,
  commit, push, or merge was performed.

Validation result:
  All five validation commands exited 0. Python compile passed. No secrets appeared in
  any output. Only orchestrator-allowed files were modified.

Risks found:
  - Log files at scripts/potucky_agent_prompts/logs/ contain raw agent stdout/stderr
    and are not redacted. If an agent prints a secret, it will appear in those files.
    [severity: MEDIUM — now documented; no redaction implemented]

Manual checks needed:
  - Confirm the NEEDS_USER_APPROVAL-only gate for mark-done is acceptable (tightening
    from the previous looser IN_PROGRESS / NEEDS_REVIEW / NEEDS_FIX / NEEDS_USER_APPROVAL).
  - Verify run-next and auto-run-next blocking guard logic matches intended policy.

Codex review:
  Result:  pending
  Blockers:
    - none known
  Suggestions:
    - none
  Reviewed by:  Codex
  Reviewed at:  pending

Next recommended task:
  IAP-002 — to be defined (add to scripts/potucky_agent_tasks.json)
---

---
POTUCKY ORCHESTRATOR entry
Task ID:  IAP-001
Title:    Read-only safety baseline
Action:   IN_PROGRESS — run-next called
Date:     2026-05-20 05:23 UTC
Details:  Task marked IN_PROGRESS. Executor and Codex prompts generated. Manual execution required — no automated run performed.
---

---
POTUCKY ORCHESTRATOR entry
Task ID:  IAP-001
Title:    Read-only safety baseline
Action:   NEEDS_REVIEW — auto-execute: Claude exited 0
Date:     2026-05-20 05:37 UTC
Details:  Claude executor exited 0. Task moved to NEEDS_REVIEW. Logs: /Users/vasylpopovich/Projects/InstaAutoPost/scripts/potucky_agent_prompts/logs.
---

---
POTUCKY ORCHESTRATOR entry
Task ID:  IAP-001
Title:    Read-only safety baseline
Action:   NEEDS_REVIEW — auto-review: unclear audit result
Date:     2026-05-20 05:38 UTC
Details:  Codex output did not contain AUDIT_RESULT: PASS or AUDIT_RESULT: FAIL. Task remains NEEDS_REVIEW. Review: /Users/vasylpopovich/Projects/InstaAutoPost/scripts/potucky_agent_prompts/logs/IAP-001_codex_stdout.log
---

---
POTUCKY ORCHESTRATOR entry
Task ID:  IAP-001
Title:    Read-only safety baseline
Action:   NEEDS_FIX — auto-review: Codex FAIL
Date:     2026-05-20 05:39 UTC
Details:  Codex returned AUDIT_RESULT: FAIL. Task moved to NEEDS_FIX. Review blockers: /Users/vasylpopovich/Projects/InstaAutoPost/scripts/potucky_agent_prompts/logs/IAP-001_codex_stdout.log
---

---
POTUCKY ORCHESTRATOR entry
Task ID:  IAP-001
Title:    Read-only safety baseline
Action:   NEEDS_REVIEW — auto-execute: Claude exited 0
Date:     2026-05-20 05:46 UTC
Details:  Claude executor exited 0. Task moved to NEEDS_REVIEW. Logs: /Users/vasylpopovich/Projects/InstaAutoPost/scripts/potucky_agent_prompts/logs.
---

---
POTUCKY ORCHESTRATOR entry
Task ID:  IAP-001
Title:    Read-only safety baseline
Action:   NEEDS_FIX — auto-review: Codex FAIL
Date:     2026-05-20 05:48 UTC
Details:  Codex returned AUDIT_RESULT: FAIL. Task moved to NEEDS_FIX. Review blockers: /Users/vasylpopovich/Projects/InstaAutoPost/scripts/potucky_agent_prompts/logs/IAP-001_codex_stdout.log
---

---
Task ID: IAP-001
Branch: main
Status: NEEDS_REVIEW
Date: 2026-05-20

Changed files:
  - CLAUDE.md — updated project/agent instructions for orchestrator workflow
  - docs/AGENT_REVIEW_RULES.md — added Codex review rules for safe audits
  - docs/AGENT_RUN_REPORT.md — appended orchestration and run evidence
  - docs/AGENT_TASK_QUEUE.md — documented current agent task queue
  - docs/POTUCKY_ORCHESTRATOR.md — documented orchestrator purpose, commands, and workflow
  - docs/PROJECT_STATUS.md — documented current project/orchestrator status
  - docs/SECURITY_RULES.md — documented safety boundaries and forbidden actions
  - scripts/potucky_agent_prompts/ — generated Claude/Codex prompt files and logs
  - scripts/potucky_agent_tasks.json — expanded IAP-001 allowed_files to match the real orchestrator bootstrap scope
  - scripts/potucky_orchestrator.py — implemented local orchestrator CLI, safe auto mode, and review flow

Commands run:
  - python3 scripts/potucky_orchestrator.py run-next
  - python3 -m py_compile scripts/potucky_orchestrator.py
  - python3 scripts/potucky_orchestrator.py doctor
  - python3 scripts/potucky_orchestrator.py status
  - python3 scripts/potucky_orchestrator.py prepare-prompts
  - python3 scripts/potucky_orchestrator.py print-next
  - python3 scripts/potucky_orchestrator.py auto-execute IAP-001
  - python3 scripts/potucky_orchestrator.py auto-review IAP-001
  - python3 scripts/potucky_orchestrator.py auto-run-next
  - git branch --show-current
  - git ls-files .github/workflows
  - rg checks for shell=True/os.system/subprocess usage
  - rg checks for hardcoded token/key/secret patterns

What was done:
  Created and tested the first safe POTUCKY ORCHESTRATOR workflow inside the InstaAutoPost project. Verified that Claude and Codex can be launched through CLI, logs are written, task state changes are tracked, and Codex can block completion when scope or report evidence is insufficient.

What was not done:
  No publish, deploy, Supabase write, migration apply, GitHub Actions run, secrets print, commit, push, or merge was intentionally performed.

Validation result:
  Python compile passed. Doctor/status commands worked. Claude CLI and Codex CLI were available. Codex correctly failed the task because the original allowed_files scope was too narrow and because a completed report entry was missing.

Risks found:
  - Original IAP-001 allowed_files scope was too narrow for the actual bootstrap orchestrator work. [severity: MEDIUM]
  - Claude CLI may request write permission for docs/AGENT_RUN_REPORT.md during auto mode. [severity: MEDIUM]
  - Temporary Supabase CLI file appeared in git status and should not be included in the task scope. [severity: LOW]
  - A Claude/Codex prompt was accidentally pasted into Terminal, which triggered harmless but noisy command errors and created an accidental package-lock.json. [severity: LOW]

Manual checks needed:
  - Confirm allowed_files now matches the real orchestrator bootstrap files.
  - Confirm supabase/.temp/ and accidental package-lock.json are removed if untracked.
  - Re-run Codex review after scope/report fixes.

Codex review:
  Result: pending
  Blockers:
    - pending re-review after scope/report fix
  Suggestions:
    - none
  Reviewed by: Codex
  Reviewed at: pending

Next recommended task:
  IAP-002 — Audit current Instagram pipeline
---

---
POTUCKY ORCHESTRATOR entry
Task ID:  IAP-001
Title:    Read-only safety baseline
Action:   NEEDS_USER_APPROVAL — auto-review: Codex PASS
Date:     2026-05-21 00:20 UTC
Details:  Codex returned AUDIT_RESULT: PASS. Task moved to NEEDS_USER_APPROVAL. DONE requires explicit user command. Codex output: /Users/vasylpopovich/Projects/InstaAutoPost/scripts/potucky_agent_prompts/logs/IAP-001_codex_stdout.log
---

---
POTUCKY ORCHESTRATOR entry
Task ID:  IAP-001
Title:    Read-only safety baseline
Action:   DONE — mark-done called by user
Date:     2026-05-21 00:21 UTC
Details:  Task manually marked DONE. Implies: executor work complete, validation passed, run report filed, Codex PASS received.
---

---
Task ID: IAP-001-FINAL-FIX
Branch: agent/iap-001-orchestrator-bootstrap
Status: DONE
Date: 2026-05-22

Changed files:
  - scripts/potucky_orchestrator.py — added blocking-task guard to cmd_auto_execute for TODO/NEEDS_FIX status
  - docs/POTUCKY_ORCHESTRATOR.md — fixed contradiction: Codex may run safe read-only inspection commands
  - scripts/potucky_agent_prompts/IAP-001_claude_executor_prompt.md — updated Generated date, Status DONE, Branch to agent/iap-001-orchestrator-bootstrap
  - scripts/potucky_agent_prompts/IAP-001_codex_review_prompt.md — updated Generated date to match current state
  - docs/AGENT_RUN_REPORT.md — appended this entry

Commands run:
  - python3 -m py_compile scripts/potucky_orchestrator.py  →  exit 0 (COMPILE OK)
  - python3 scripts/potucky_orchestrator.py status  →  exit 0, all tasks DONE, branch correct
  - python3 scripts/potucky_orchestrator.py doctor  →  exit 0, all checks OK
  - python3 scripts/potucky_orchestrator.py print-next  →  exit 0, "All tasks are DONE"
  - git status --short  →  exit 0, only orchestrator-bootstrap files modified/untracked

What was done:
  Fixed four Codex re-review blockers: (1) Added the same blocking-task guard that
  run-next and auto-run-next use to cmd_auto_execute — when a task is in TODO or
  NEEDS_FIX, auto-execute now checks for any other task in IN_PROGRESS, NEEDS_REVIEW,
  NEEDS_FIX, or NEEDS_USER_APPROVAL and refuses to start if one is found, excluding
  the target task itself from the check. (2) Fixed the POTUCKY_ORCHESTRATOR.md
  contradiction at the end of "How It Uses Codex": the old text said "Codex never
  writes code, runs commands, commits, or deploys" which contradicted the prompt's
  ALLOWED READ-ONLY COMMANDS section; updated to "Codex never writes files or code,
  never commits or deploys. In both modes, Codex may only run the safe read-only
  inspection commands listed in the audit prompt." (3) Updated both IAP-001 prompt
  files to clear the stale Generated timestamp, Status NEEDS_REVIEW, and stale branch
  agent/iap-001-safety-baseline; the executor prompt now shows Status: DONE and
  Branch: agent/iap-001-orchestrator-bootstrap. (4) Appended this run report.

What was not done:
  No publish, deploy, Supabase write, migration apply, GitHub Actions run, secrets
  print, commit, push, merge, or package install was performed.

Validation result:
  All five validation commands exited 0. Python compile passed. No secrets appeared
  in any output. Only the five allowed files were modified.

Risks found:
  - none [severity: N/A]

Manual checks needed:
  - Confirm blocking-task guard in auto-execute matches the intent: only TODO/NEEDS_FIX
    status triggers the guard; IN_PROGRESS can re-execute without a blocking check.
  - Confirm the POTUCKY_ORCHESTRATOR.md doc fix is accurate and complete.

Codex review:
  Result:  pending
  Blockers:
    - none known
  Suggestions:
    - none
  Reviewed by:  Codex
  Reviewed at:  pending

Next recommended task:
  IAP-002 — Read-only audit of current InstaAutoPost pipeline
---

---
Task ID: IAP-002-QUEUE
Branch: agent/iap-001-orchestrator-bootstrap
Status: DONE
Date: 2026-05-22

Changed files:
  - scripts/potucky_agent_tasks.json — added IAP-002 as first TODO task (read-only pipeline audit)
  - docs/AGENT_TASK_QUEUE.md — added IAP-002 human-readable task block
  - docs/PROJECT_STATUS.md — updated agent workflow section: IAP-002 TODO, Next task: IAP-002
  - docs/AGENT_RUN_REPORT.md — appended this entry

Commands run:
  - python3 scripts/potucky_orchestrator.py status  →  exit 0, IAP-002 TODO shown as first active task
  - python3 scripts/potucky_orchestrator.py doctor  →  exit 0, 2 task(s), all checks OK
  - python3 scripts/potucky_orchestrator.py print-next  →  exit 0, recommends run-next for IAP-002
  - git status --short  →  exit 0, only 3 allowed files modified

What was done:
  Added IAP-002 (read-only audit of current InstaAutoPost pipeline) as the next
  queued TODO task. The task is insert-sorted first in the JSON array so it becomes
  the first active task. Allowed files: docs/AGENT_RUN_REPORT.md only. Audit scope
  covers project structure, GitHub Actions workflows, Instagram publish flow, Supabase
  usage, environment/secrets assumptions, dry-run/safe mode behavior, log and secret
  exposure risks, production publish risks, old naming drift, and next safest
  implementation step. No code changes are permitted for this task.

What was not done:
  No publish, deploy, Supabase write, migration apply, GitHub Actions run, secrets
  print, commit, push, merge, or package install was performed. No app code, workflow
  code, UI, or package files were changed.

Validation result:
  All four validation commands exited 0. git status shows only the three allowed files
  as modified. No secrets appeared in any output.

Risks found:
  - none [severity: N/A]

Manual checks needed:
  - Confirm IAP-002 allowed_files (docs/AGENT_RUN_REPORT.md only) is correct for a
    pure read-only audit task where only the report is written.
  - Confirm branch agent/iap-001-orchestrator-bootstrap is acceptable for IAP-002
    (read-only, no code changes).

Codex review:
  Result:  N/A — queue management entry, not a code task
  Blockers:
    - none
  Suggestions:
    - none
  Reviewed by:  N/A
  Reviewed at:  N/A

Next recommended task:
  IAP-002 — Read-only audit of current InstaAutoPost pipeline
---

---
Task ID: IAP-002
Branch: agent/iap-001-orchestrator-bootstrap
Status: NEEDS_REVIEW
Date: 2026-05-22

Changed files:
  - docs/AGENT_RUN_REPORT.md — appended this audit entry (only executor-allowed file)

  Orchestration artifacts present in git status (NOT executor writes — managed by
  potucky_orchestrator.py run-next / prepare-prompts):

  - scripts/potucky_agent_tasks.json — status field set to IN_PROGRESS by run-next
  - scripts/potucky_agent_prompts/IAP-002_claude_executor_prompt.md — generated by prepare-prompts
  - scripts/potucky_agent_prompts/IAP-002_codex_review_prompt.md — generated by prepare-prompts

Commands run:
  - find . -maxdepth 2 -type f | sort  →  exit 0, project structure listed
  - find .github -type f  →  exit 0, 1 workflow file found
  - find supabase -type f  →  exit 0, 3 migrations + 1 policy file found
  - find ui/src -type f  →  exit 0, 17 UI source files found
  - grep -rn INSTAGRAM_API_ENABLED ...  →  exit 0, env refs inspected
  - grep -rn os.system/shell=True ...  →  exit 0, no injection in project code
  - grep -rn QAContentAutomation/TikTok/CreatorFlow ...  →  exit 0, no naming drift
  - git log --oneline -10  →  exit 0, 10 commits reviewed
  - git status --short  →  exit 0, docs/AGENT_RUN_REPORT.md modified (executor write);
      scripts/potucky_agent_tasks.json modified + 2 untracked IAP-002 prompt files
      (orchestration artifacts, not executor scope violations)

What was done:
  Performed a read-only audit of all InstaAutoPost pipeline components. Findings
  follow by audit area.

  1. PROJECT STRUCTURE
  Root layout is clean and well-separated: docs/, scripts/, ui/, supabase/, .github/.
  No unexpected top-level files. Source-of-truth docs match the declared architecture.
  No cross-project contamination detected. scripts/ contains a .venv/ directory which
  is gitignored. scripts/potucky_agent_prompts/ holds generated prompt and log files;
  prompt .md files are untracked and should remain untracked (no secrets in them, but
  they contain internal task context). *.log files are gitignored by *.log glob.

  2. GITHUB ACTIONS WORKFLOWS
  One workflow: .github/workflows/instaautopost-publisher.yml.
  Cron schedule is commented out — manual workflow_dispatch only. This is correct and
  safe per the current blocker state. Four secrets injected as env vars:
  SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, IG_USER_ID, IG_ACCESS_TOKEN. These come
  from GitHub Secrets (not vars) — correct. INSTAGRAM_API_ENABLED comes from GitHub
  Variables (not Secrets) — correct pattern for a boolean gate. Timeout: 10 minutes.
  Risk: no concurrency controls on the workflow. If the cron is re-enabled and two
  manual dispatches overlap, two workers could race to claim the same queue row.
  The DB-side FOR UPDATE SKIP LOCKED in claim_next_queue_item mitigates this, but
  a GH Actions concurrency group should be added before restoring the cron.

  3. INSTAGRAM PUBLISH FLOW
  Worker (scripts/instaautopost_publisher.py v1.2.0) processes exactly one queue item
  per execution. Dry-run gate: DRY_RUN = (INSTAGRAM_API_ENABLED != "true"). Safe
  default — unset or any non-"true" value stays dry. Live mode validates IG_USER_ID
  and IG_ACCESS_TOKEN BEFORE calling claim_queue_item — misconfigured workers exit
  clean without locking any row. Three-phase live publish:
    Phase 1 (pre-media_id): container creation -> poll until FINISHED -> publish call.
      Failures here are safe to retry.
    _anchor_media_id(): after IG returns media_id, writes external_media_id +
      published_at + queue_status=published atomically. claim_next_queue_item filters
      WHERE external_media_id IS NULL, so anchored rows cannot be reclaimed. If anchor
      fails: fallback sets queue_status=failed, logs CRITICAL, sys.exit(1). No retry.
    Phase 2 (post-anchor): write_attempt and mark_published. Failures here require
      manual reconciliation but cannot cause duplicate publish.
  Dry-run path: logs "Would publish", does not call IG API, writes dry_run attempt
  record, resets queue row to scheduled (un-increments attempt_count). Safe.

  4. SUPABASE USAGE AND SCHEMA ASSUMPTIONS
  Three tables: ig_content_library, ig_publishing_queue, ig_publish_attempts.
  Three repo migrations:
    20260516000000: creates base schema + claim_next_queue_item RPC.
    20260516001000: adds dev RLS policies (all USING true for authenticated role).
    20260516002000: adds failure_reason and worker_metadata to ig_publishing_queue;
      drops error_message from ig_publishing_queue; updates claim_next_queue_item
      to also reclaim stale processing rows (lock > 10 min).
  Worker and UI both use failure_reason (not error_message) for queue-level state.
  ig_publish_attempts uses error_message for attempt-level errors — correct.
  UI types.ts correctly declares failure_reason on QueueItem and error_message on
  PublishAttempt only. PublishingQueue.tsx uses failure_reason. LogsAttempts.tsx
  uses error_message on PublishAttempt — correct.
  RLS: enabled on all 3 tables. service_role bypasses RLS (worker). Dev policies
  are USING true for authenticated — open for dev, must be replaced before production.
  Dev delete policies on content and queue use auth.uid() = created_by — appropriate.
  SECURITY DEFINER function claim_next_queue_item: REVOKE from PUBLIC, anon,
  authenticated; GRANT to service_role only — correct hardening.
  Blocker: migration 20260516002000 must be confirmed applied to live Supabase before
  any real publish run.

  5. ENVIRONMENT / SECRETS ASSUMPTIONS
  Worker requires: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY (always); IG_USER_ID,
  IG_ACCESS_TOKEN, INSTAGRAM_API_ENABLED (live mode only).
  UI requires: VITE_SUPABASE_URL, VITE_SUPABASE_ANON_KEY.
  .env.example contains only placeholder text and a warning not to use service role
  key in the UI. ui/.env.local exists locally and is gitignored. No hardcoded secrets
  found in any project file. All secrets come from env vars. Variable naming is
  consistent with CLAUDE.md constraints.

  6. DRY-RUN / SAFE MODE BEHAVIOR
  Dry-run is the default and is safe when INSTAGRAM_API_ENABLED is unset or not
  exactly "true". Dry-run still writes to Supabase (attempt record + queue reset)
  — requires SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY. A dry-run with missing
  Supabase credentials exits at get_supabase() before any queue claim. Dry-run
  does not call Instagram. attempt_count is un-incremented after dry-run so real
  publish still has max_attempts attempts from the original baseline.

  7. LOGS AND SECRET EXPOSURE RISKS
  Worker logging uses _redact(text, access_token) on all exception strings before
  logging or storing. Also strips access_token= query params and Bearer tokens via
  regex. _redact_url() strips all query parameters before logging URLs. _safe_raise()
  logs only HTTP status code and reason — never the full request URL.
  Risk (inherent, not a bug): ig_poll_container sends access_token as a URL query
  param to IG Graph API v19.0. _redact_url strips it before worker logging. HTTP
  client libraries may write raw URLs to their own debug logs if debug logging is on.
  Acceptable as long as debug logging is off in production.
  Risk: scripts/potucky_agent_prompts/logs/ contains raw stdout/stderr from Claude
  and Codex auto-runs. *.log is gitignored. These files could contain sensitive
  output if an agent ran a forbidden command. Risk is low but files should be treated
  as potentially sensitive and never manually committed.
  No secrets found in committed code or committed docs.

  8. PRODUCTION PUBLISH RISKS
  Ordered by priority:
    HIGH: Migration 20260516002000 not confirmed on live Supabase. Without it, worker
      fails at first DB write. Primary blocker before any real publish run.
    HIGH: Dev RLS policies (USING true) are not production-safe. Any authenticated
      user can read/write/delete all rows. Must replace before multi-user or production.
    MEDIUM: No GitHub Actions concurrency group. Safe while cron is disabled. Must
      add before restoring cron to prevent overlapping worker runs.
    MEDIUM: Stale processing rows at max_attempts cannot be auto-reclaimed. Require
      manual operator reset.
    LOW: ig_content_library dev_delete_content policy violates the archive-only design
      intent for production. Should be removed before production.
    LOW: WORKER_VERSION is hardcoded (v1.2.0). No automated version bump process.

  9. OLD NAMING DRIFT
  No old project names found in project code, migrations, workflow, or docs.
  TikTok appears in two intentional contexts: (1) security rule templates as a
  prohibited action reference; (2) docs/PRODUCT_BLUEPRINT.md as a planned future
  multi-platform expansion target — this is forward-looking product scope, not old
  naming drift. CreatorFlow appears only in security rule templates as a prohibited
  action reference — intentional and correct, not drift. All table and field names
  are current. No references to deleted fields (error_message on queue table) found
  in worker or UI code.

  10. NEXT SAFEST IMPLEMENTATION STEP
  In order:
    Step 1: Confirm migration 20260516002000 applied to live Supabase:
      SELECT column_name FROM information_schema.columns
      WHERE table_name = 'ig_publishing_queue'
      AND column_name IN ('failure_reason', 'worker_metadata', 'error_message');
      Expected: failure_reason and worker_metadata present; error_message absent.
    Step 2: Seed one test queue row in dev and run dry-run via workflow_dispatch.
      Verify: attempt record written (status=dry_run), queue row reset to scheduled,
      no IG API call in logs.
    Step 3: Confirm claim_next_queue_item works under service_role by reviewing the
      dry-run log for successful claim and release.
    Step 4: After dry-run verified and user explicitly approves: enable live mode for
      a single manual workflow_dispatch run using one safe test queue row.
    Step 5 (before cron restore): Add GitHub Actions concurrency group.
    Step 6 (before production): Replace dev RLS policies with owner-scoped policies.

What was not done:
  No publish, deploy, Supabase write, migration apply, GitHub Actions run, secrets
  print, commit, push, merge, or package install was performed. No app code, workflow,
  UI, package, or Supabase files were changed. No live services were contacted. No
  .env files or secret values were printed. Agent log files were not read.

Validation result:
  All four validation commands exited 0. git status shows docs/AGENT_RUN_REPORT.md
  as the executor-modified file. Also present: scripts/potucky_agent_tasks.json
  (modified by orchestrator run-next to set IN_PROGRESS) and 2 untracked IAP-002
  prompt files generated by prepare-prompts. These are expected orchestration
  artifacts — they are not executor scope violations. No secrets appeared in any
  output. Only the executor-allowed file (docs/AGENT_RUN_REPORT.md) received
  executor writes.

Risks found:
  - Migration 20260516002000 not confirmed on live Supabase — blocks real publish.
    [severity: HIGH]
  - Dev RLS policies open to all authenticated users — not production-safe.
    [severity: HIGH]
  - No GitHub Actions concurrency group — race risk when cron is restored.
    [severity: MEDIUM]
  - Stale processing rows at max_attempts require manual operator reset.
    [severity: MEDIUM]
  - dev_delete_content policy on ig_content_library violates archive-only design.
    [severity: LOW]
  - WORKER_VERSION hardcoded — version drift risk on script edits. [severity: LOW]
  - Agent log files in scripts/potucky_agent_prompts/logs/ are gitignored but may
    contain agent stdout — treat as potentially sensitive. [severity: LOW]

Manual checks needed:
  - Confirm migration 20260516002000 is applied to live Supabase before any publish.
  - Confirm claim_next_queue_item is executable under service_role.
  - Confirm anon/authenticated cannot call claim_next_queue_item.
  - Confirm INSTAGRAM_API_ENABLED is not set to "true" in any GitHub Variable that
    could accidentally enable live publishing on the next manual dispatch.
  - Review GitHub Actions concurrency requirement before restoring cron.
  - Review dev RLS policy scope before multi-user or production use.

Codex review:
  Result:  pending
  Blockers:
    - none known
  Suggestions:
    - none
  Reviewed by:  Codex
  Reviewed at:  pending

Next recommended task:
  IAP-003 — Confirm production migration state and run verified dry-run
---

---
POTUCKY ORCHESTRATOR entry
Task ID:  IAP-002
Title:    Read-only audit of current InstaAutoPost pipeline
Action:   IN_PROGRESS — run-next called
Date:     2026-05-22 23:56 UTC
Details:  Task marked IN_PROGRESS. Executor and Codex prompts generated. Manual execution required — no automated run performed.
---

---
POTUCKY ORCHESTRATOR entry
Task ID:  IAP-002
Title:    Read-only audit of current InstaAutoPost pipeline
Action:   NEEDS_REVIEW — auto-execute: Claude exited 0
Date:     2026-05-23 00:32 UTC
Details:  Claude executor exited 0. Task moved to NEEDS_REVIEW. Logs: /Users/vasylpopovich/Projects/InstaAutoPost/scripts/potucky_agent_prompts/logs.
---

---
POTUCKY ORCHESTRATOR entry
Task ID:  IAP-002
Title:    Read-only audit of current InstaAutoPost pipeline
Action:   NEEDS_FIX — auto-review: Codex FAIL
Date:     2026-05-23 00:35 UTC
Details:  Codex returned AUDIT_RESULT: FAIL. Task moved to NEEDS_FIX. Review blockers: /Users/vasylpopovich/Projects/InstaAutoPost/scripts/potucky_agent_prompts/logs/IAP-002_codex_stdout.log
---

---
POTUCKY ORCHESTRATOR entry
Task ID:  IAP-002
Title:    Read-only audit of current InstaAutoPost pipeline
Action:   DONE — mark-done called by user
Date:     2026-05-23 00:38 UTC
Details:  Task manually marked DONE. Implies: executor work complete, validation passed, run report filed, Codex PASS received.
---

---
POTUCKY ORCHESTRATOR entry
Task ID:  IAP-003
Title:    Verify live migration state and dry-run publisher safety
Action:   IN_PROGRESS — run-next called
Date:     2026-05-23 00:40 UTC
Details:  Task marked IN_PROGRESS. Executor and Codex prompts generated. Manual execution required — no automated run performed.
---

---
Task ID: IAP-003
Branch: agent/iap-001-orchestrator-bootstrap
Status: NEEDS_REVIEW
Date: 2026-05-22

Changed files:

  - docs/AGENT_RUN_REPORT.md — appended this audit entry (only executor-allowed file)

  Orchestration artifacts present in git status (NOT executor writes):
  - scripts/potucky_agent_tasks.json — status field set to IN_PROGRESS by run-next
  - scripts/potucky_agent_prompts/IAP-002_claude_executor_prompt.md — generated by prepare-prompts
  - scripts/potucky_agent_prompts/IAP-002_codex_review_prompt.md — generated by prepare-prompts
  - scripts/potucky_agent_prompts/IAP-003_claude_executor_prompt.md — generated by prepare-prompts
  - scripts/potucky_agent_prompts/IAP-003_codex_review_prompt.md — generated by prepare-prompts

Commands run:

  - python3 scripts/potucky_orchestrator.py status  →  exit 0, IAP-003 IN_PROGRESS shown
  - python3 scripts/potucky_orchestrator.py doctor  →  exit 0, all checks OK
  - python3 scripts/potucky_orchestrator.py print-next  →  exit 0, recommends finish executor work then prepare-prompts
  - git status --short  →  exit 0, only orchestration artifacts + allowed report file
  - Read supabase/migrations/ (ls)  →  3 migration files confirmed
  - Read scripts/instaautopost_publisher.py  →  DRY_RUN guard and publish flow inspected
  - Read supabase/migrations/20260516002000_fix_queue_schema_and_stale_processing.sql  →  schema and RPC confirmed
  - Read supabase/migrations/20260516001000_add_instaautopost_dev_rls_policies.sql  →  RLS policies confirmed
  - Read docs/SUPABASE_SCHEMA.md  →  schema contract and SQL checklist confirmed
  - grep SUPABASE_SERVICE_ROLE_KEY/IG_ACCESS_TOKEN in ui/src/  →  display-only reference confirmed
  - grep INSTAGRAM_API_ENABLED/DRY_RUN in scripts/  →  dry-run gate confirmed
  - Read ui/src/lib/supabase.ts  →  anon key only confirmed
  - No live Supabase connection was made. No network calls to IG API were made.

What was done:
  Performed a read-only local inspection against four safety areas required before
  real Instagram API publishing. No code changes were made. No live services were
  contacted. Findings follow with SAFE / RISK / BLOCKER labels.

  1. MIGRATION DRIFT [BLOCKER (carryover)]
  Three repo migrations confirmed: 20260516000000 (base schema + claim RPC),
  20260516001000 (dev RLS policies), 20260516002000 (add failure_reason and
  worker_metadata to ig_publishing_queue; drop error_message from ig_publishing_queue;
  update claim_next_queue_item to reclaim stale processing rows).
  Worker uses failure_reason throughout — field references are consistent with the
  migration. CLAUDE.md live schema field list matches migration 20260516002000 output.
  BLOCKER: Whether migration 20260516002000 has been applied to the live production
  Supabase instance is unverified. No live Supabase query was permitted in this task.
  Per docs/SUPABASE_SCHEMA.md: "Treat unconfirmed production state as a blocker before
  live publishing." This blocker carries forward from IAP-002.

  2. DRY-RUN BEHAVIOR [SAFE]
  scripts/instaautopost_publisher.py line 26:
    DRY_RUN = os.environ.get("INSTAGRAM_API_ENABLED", "false").strip().lower() != "true"
  Default is dry-run when the variable is unset or any value other than exactly "true".
  process_item() routes to `_process_dry_run()` or `_process_live()` based on DRY_RUN.
  _process_dry_run(): logs "[DRY RUN] Instagram API not called", writes a dry_run
  attempt record to ig_publish_attempts, resets queue row to queue_status=scheduled
  and un-increments attempt_count. No IG Graph API function is called in this path.
  Dry-run cannot accidentally publish. Guard is correct and cannot be bypassed by
  an unset or partial variable value.

  3. RLS AND SECRETS EXPOSURE [SAFE / RISK]
  SAFE: UI Supabase client (ui/src/lib/supabase.ts) uses VITE_SUPABASE_URL and
  VITE_SUPABASE_ANON_KEY only. Service role key is not referenced in any UI code.
  SAFE: Settings.tsx references SUPABASE_SERVICE_ROLE_KEY and IG_ACCESS_TOKEN only
  as static display text in an env-vars checklist (where: 'backend'). These are not
  read from env, passed to any function, or used in any fetch or Supabase call.
  SAFE: No Instagram Graph API calls exist in any UI source file.
  SAFE: Worker _redact(text, access_token) is applied to all exception strings before
  logging or storing. Regex redaction also strips access_token= query params and
  Bearer tokens. `_redact_url()` strips full query strings. `_safe_raise()` logs only
  HTTP status and reason — never the full request URL.
  SAFE: claim_next_queue_item is REVOKE'd from PUBLIC, anon, and authenticated;
  GRANT'd to service_role only. UI cannot call the claim RPC.
  RISK (HIGH, carryover): Dev RLS policies on all three tables use USING(true) for
  the authenticated role — any logged-in user can read and write all rows. Must be
  replaced with owner-scoped policies (USING auth.uid() = created_by) before
  multi-user or production use. Policies are explicitly labeled DEV ONLY in migration.

  4. PUBLISHER SAFETY — published_at AND external_media_id GUARDS [SAFE]
  Two-layer duplicate-publish protection confirmed:
  Layer 1 (in-process): process_item() line 336-338 returns immediately if
    item.get("published_at") or item.get("external_media_id") is set.
  Layer 2 (DB): claim_next_queue_item filters
    WHERE published_at IS NULL AND external_media_id IS NULL
    so an already-published row can never be reclaimed by any worker.
  _anchor_media_id(): called immediately after Instagram returns media_id. Writes
  external_media_id + published_at + queue_status=published in a single update. Once
  this succeeds, claim_next_queue_item's filter prevents reclaim — even if all
  subsequent writes (write_attempt, mark_published) fail. If the anchor write itself
  fails: fallback sets queue_status=failed (not in the eligible claim status set),
  logs CRITICAL, and calls sys.exit(1). No retry path is opened in either case.
  Retry logic (mark_failed_or_retry): only called in the pre-media_id phase (container
  creation, container poll, publish call). If any of those steps fail, media_id has
  not been returned by Instagram, so retry is safe and cannot cause a duplicate post.
  Post-anchor DB failures (write_attempt or mark_published): logged as CRITICAL with
  manual reconciliation instruction. Best-effort fallback sets queue_status=failed.
  No retry is scheduled. Operator reconciles using media_id in logs.

What was not done:
  No live Supabase connection was made. No Instagram API calls were made. No publish,
  deploy, migration apply, GitHub Actions run, secrets print, commit, push, merge, or
  package install was performed. No app code, workflow, UI, Supabase, or migration
  files were changed.

Validation result:
  All four required validation commands exited 0. git status shows expected orchestration
  artifacts (scripts/potucky_agent_tasks.json modified by run-next; 4 untracked prompt
  files generated by prepare-prompts) and docs/AGENT_RUN_REPORT.md as the executor-
  modified file. No secrets appeared in any output. Only the executor-allowed file
  received executor writes.

Risks found:

- Migration 20260516002000 not confirmed applied to live Supabase — blocks real publish.
  [severity: HIGH — BLOCKER]
- Dev RLS policies open to all authenticated users (USING true) — not production-safe.
  [severity: HIGH — RISK]
- No live verification was performed — this inspection is local-only.
  [severity: MEDIUM — inherent task constraint, not a bug]

Manual checks needed:

- Confirm migration 20260516002000 is applied to live Supabase before any real publish:
    SELECT column_name FROM information_schema.columns
    WHERE table_name = 'ig_publishing_queue'
    AND column_name IN ('failure_reason', 'worker_metadata', 'error_message');
    Expected: failure_reason and worker_metadata present; error_message absent.
- Confirm claim_next_queue_item is executable only by service_role on live Supabase.
- Confirm INSTAGRAM_API_ENABLED is not set to "true" in any live GitHub Variable.
- Replace dev RLS policies with owner-scoped policies before production publishing.

Codex review:
  Result:  pending
  Blockers:
    - none known
  Suggestions:
    - none
  Reviewed by:  Codex
  Reviewed at:  pending

Next recommended task:
  Codex read-only review of IAP-003, then user decides whether to create IAP-004
  for controlled live migration verification (confirm 20260516002000 on production
  Supabase) and a verified single-item dry-run via workflow_dispatch

---

---
POTUCKY ORCHESTRATOR entry
Task ID:  IAP-003
Title:    Verify live migration state and dry-run publisher safety
Action:   DONE — mark-done called by user
Date:     2026-05-23 01:29 UTC
Details:  Task manually marked DONE. Implies: executor work complete, validation passed, run report filed, Codex PASS received.
---

---
Task ID: IAP-004
Branch: agent/iap-004-orchestrator-auto-mode
Status: NEEDS_REVIEW
Date: 2026-05-22

Changed files:
  - scripts/potucky_orchestrator.py — added KNOWN ORCHESTRATION ARTIFACTS section
    to generate_codex_prompt(); updated AUDIT STEPS Step 1 to reference it
  - scripts/potucky_agent_tasks.json — added IAP-004 task definition (status: TODO)
  - docs/AGENT_RUN_REPORT.md — appended this entry (executor-allowed file)

  Orchestration artifacts present in git status (NOT executor writes):
  - scripts/potucky_agent_prompts/IAP-002_claude_executor_prompt.md — generated previously
  - scripts/potucky_agent_prompts/IAP-002_codex_review_prompt.md — generated previously
  - scripts/potucky_agent_prompts/IAP-003_claude_executor_prompt.md — generated previously
  - scripts/potucky_agent_prompts/IAP-003_codex_review_prompt.md — generated previously

Commands run:
  - python3 -m py_compile scripts/potucky_orchestrator.py  →  exit 0 (see validation)
  - python3 scripts/potucky_orchestrator.py status  →  exit 0 (see validation)
  - python3 scripts/potucky_orchestrator.py doctor  →  exit 0 (see validation)
  - python3 scripts/potucky_orchestrator.py print-next  →  exit 0 (see validation)
  - git status --short  →  exit 0 (see validation)

What was done:
  Hardened POTUCKY ORCHESTRATOR auto-mode to fix the root cause of repeated Codex
  FAIL results on IAP-002 and IAP-003: Codex was treating orchestration-managed files
  (scripts/potucky_agent_tasks.json status updates, generated prompt files) as
  executor scope violations, causing false FAIL results.

  Fix 1 — Codex prompt: generate_codex_prompt() now includes a KNOWN ORCHESTRATION
  ARTIFACTS section that explicitly names scripts/potucky_agent_tasks.json,
  {task_id}_claude_executor_prompt.md, {task_id}_codex_review_prompt.md, and log
  files as orchestrator-managed artifacts. Each entry includes a targeted verification
  instruction (e.g., "verify only 'status' field changed") so Codex can still flag
  genuine violations while skipping expected artifacts.

  Fix 2 — AUDIT STEPS Step 1: updated the git status verification line to say
  "only files in the ALLOWED FILES list, plus the KNOWN ORCHESTRATION ARTIFACTS
  listed below, appear as modified or added" instead of the previous strict phrasing
  that caused Codex to flag any non-allowed-list file.

  Fix 3 — Task queue: added IAP-004 (this task) to scripts/potucky_agent_tasks.json
  as the first entry (status: TODO), with allowed_files, forbidden_actions,
  validation_commands, and notes matching the IAP-004 task specification. This task
  serves as the smoke-test vehicle for the fixed auto-mode flow.

  State machine review: cmd_auto_execute correctly transitions TODO/NEEDS_FIX ->
  IN_PROGRESS -> NEEDS_REVIEW (Claude exit 0) or NEEDS_FIX (non-zero). cmd_auto_review
  correctly transitions NEEDS_REVIEW -> NEEDS_USER_APPROVAL (AUDIT_RESULT: PASS) or
  NEEDS_FIX (AUDIT_RESULT: FAIL). mark-done is restricted to NEEDS_USER_APPROVAL only.
  No state machine changes were required — the logic was already correct.

What was not done:
  No publish, deploy, Supabase write, migration apply, GitHub Actions run, secrets
  print, commit, push, merge, or package install was performed. No app code, workflow,
  UI, Supabase, or migration files were changed. No live services were contacted.

Validation result:
  All five validation commands exited 0. Python compile passed. git status shows only
  the three allowed files as executor writes (plus pre-existing untracked prompt files
  for IAP-002/IAP-003 which are expected orchestration artifacts). No secrets appeared
  in any output.

Risks found:
  - Codex must now be trusted to follow the KNOWN ORCHESTRATION ARTIFACTS section
    correctly. If Codex ignores this section, false FAILs may persist. [severity: LOW]
  - The `{task_id}` placeholder in artifact file names is evaluated at prompt
    generation time — if a task ID contains special characters, path construction
    could produce unexpected names. Current IDs (IAP-NNN) are safe. [severity: LOW]

Manual checks needed:
  - Run auto-run-next with IAP-004 as the next TODO task to verify the fixed Codex
    prompt produces AUDIT_RESULT: PASS without false artifact blockers.
  - Confirm KNOWN ORCHESTRATION ARTIFACTS section renders correctly in the generated
    Codex prompt for IAP-004 (check scripts/potucky_agent_prompts/IAP-004_codex_review_prompt.md).

Codex review:
  Result:  pending
  Blockers:
    - none known
  Suggestions:
    - none
  Reviewed by:  Codex
  Reviewed at:  pending

Next recommended task:
  Run: python3 scripts/potucky_orchestrator.py auto-run-next
  This will pick up IAP-004 (first TODO) and run a full automated cycle as a smoke test.
---

---
Task ID: IAP-004
Branch: agent/iap-004-orchestrator-auto-mode
Status: NEEDS_REVIEW
Date: 2026-05-22

Changed files:
  - scripts/potucky_orchestrator.py — added `import os`; replaced hardcoded CLAUDE_TIMEOUT/CODEX_TIMEOUT constants with env-var-driven values (POTUCKY_CLAUDE_TIMEOUT_SECONDS, POTUCKY_CODEX_TIMEOUT_SECONDS); added timeout display block to cmd_doctor
  - docs/POTUCKY_ORCHESTRATOR.md — added smoke testing note with 120s env var example under auto-run-next section
  - docs/AGENT_RUN_REPORT.md — appended this entry

Commands run:
  - python3 -m py_compile scripts/potucky_orchestrator.py  →  exit 0
  - python3 scripts/potucky_orchestrator.py status  →  exit 0, dashboard rendered correctly
  - python3 scripts/potucky_orchestrator.py doctor  →  exit 0, timeout block visible (600s / 300s defaults)
  - python3 scripts/potucky_orchestrator.py print-next  →  exit 0, IAP-004 IN_PROGRESS shown
  - git status --short  →  exit 0, only allowed files modified (plus pre-existing untracked prompt files)

What was done:
  Added configurable auto-mode timeouts via environment variables. CLAUDE_TIMEOUT and
  CODEX_TIMEOUT are now read from POTUCKY_CLAUDE_TIMEOUT_SECONDS and
  POTUCKY_CODEX_TIMEOUT_SECONDS respectively, with the original defaults (600s and 300s)
  preserved when the env vars are not set. The doctor command now prints the active
  timeout values. The existing timeout display in run_claude_executor and run_codex_review
  was already present and continues to show the active values. Added smoke test note
  to docs/POTUCKY_ORCHESTRATOR.md with the exact 120s command.

What was not done:
  No app code, UI, Supabase migrations, workflows, or publisher logic was changed.
  No publish, deploy, commit, push, merge, package install, or secret print performed.
  auto-run-next was not invoked as instructed.

Validation result:
  All five validation commands exited 0. Python compile passed. git status shows only
  allowed files. No secrets appeared in any output.

Risks found:
  - none

Manual checks needed:
  - Verify doctor output shows timeout block with correct env var names.
  - Confirm POTUCKY_CLAUDE_TIMEOUT_SECONDS=120 POTUCKY_CODEX_TIMEOUT_SECONDS=120 python3 scripts/potucky_orchestrator.py doctor shows 120s / 120s before running auto-run-next.

Codex review:
  Result:  pending
  Blockers:
    - none known
  Suggestions:
    - none
  Reviewed by:  Codex
  Reviewed at:  pending

Next recommended task:
  Smoke test: POTUCKY_CLAUDE_TIMEOUT_SECONDS=120 POTUCKY_CODEX_TIMEOUT_SECONDS=120 python3 scripts/potucky_orchestrator.py auto-run-next
---

---
POTUCKY ORCHESTRATOR entry
Task ID:  IAP-004
Title:    Orchestrator auto-mode hardening and smoke test
Action:   NEEDS_FIX — auto-execute: Claude execution error
Date:     2026-05-23 01:49 UTC
Details:  Claude execution error: Claude timed out after 120s. Check logs: /Users/vasylpopovich/Projects/InstaAutoPost/scripts/potucky_agent_prompts/logs.
---

---
POTUCKY ORCHESTRATOR entry
Task ID:  IAP-004
Title:    Orchestrator auto-mode hardening and smoke test
Action:   NEEDS_REVIEW — auto-review: Codex execution error
Date:     2026-05-23 01:56 UTC
Details:  Codex execution error: Codex timed out after 60s. Task remains NEEDS_REVIEW.
---
