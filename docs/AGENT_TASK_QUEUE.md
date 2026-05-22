# AGENT_TASK_QUEUE.md

Agent task queue for InstaAutoPost. One task at a time. No next task starts until the current task is DONE or BLOCKED.

> POTUCKY ORCHESTRATOR uses `scripts/potucky_agent_tasks.json` as the executable task queue and this Markdown file as the human-readable workflow reference.

---

## Statuses

| Status | Meaning |
|---|---|
| `TODO` | Not yet started. |
| `IN_PROGRESS` | Active — one agent working, branch open. |
| `NEEDS_REVIEW` | Implementation done, awaiting Codex review. |
| `NEEDS_FIX` | Codex returned FAIL; agent must fix before re-review. |
| `DONE` | Implementation verified, run report complete, Codex PASS. |
| `BLOCKED` | Cannot proceed — missing info, permission, or dependency. |

---

## Strict Rules

1. **Work only on the first TODO task.** Do not skip ahead.
2. **Do not start the next task until the current task is DONE or BLOCKED.**
3. **DONE requires all four:** implementation complete, validation commands passed, run report filed in `docs/AGENT_RUN_REPORT.md`, and Codex review PASS.
4. **If Codex returns FAIL,** move task to `NEEDS_FIX`. Fix issues. Re-submit for review. Do not advance queue.
5. **If required info or permission is missing,** move task to `BLOCKED`. Document the blocker. Wait for user.
6. **One task = one branch** when code changes are involved. Branch name follows `agent/<task-id>-<slug>`.
7. **No broad refactors** unless the task explicitly permits them in its Scope field.
8. **Do not modify files outside the task's `Allowed files` list.**

---

## Task Template

```
Task ID:          IAP-XXX
Title:            <short title>
Status:           TODO | IN_PROGRESS | NEEDS_REVIEW | NEEDS_FIX | DONE | BLOCKED
Owner Agent:      Claude Code | Codex
Branch:           agent/iap-xxx-<slug>  (or N/A for doc-only tasks)
Goal:             <one paragraph — what success looks like>
Scope:
  - <bullet list of what is in scope>
Allowed files:
  - <explicit list of files or paths the agent may read or write>
Forbidden actions:
  - <explicit list of what is prohibited for this task>
Validation commands:
  - <exact shell commands to verify the task is done correctly>
Expected result:
  - <what the validation commands must produce>
Required run report:
  - File: docs/AGENT_RUN_REPORT.md
  - Fields: all
Codex review result:  pending | PASS | FAIL
Final status:         <set after Codex review>
```

---

## Task Queue

### IAP-002 — Read-only audit of current InstaAutoPost pipeline

```
Task ID:      IAP-002
Title:        Read-only audit of current InstaAutoPost pipeline
Status:       TODO
Owner Agent:  Claude Code (executor) + Codex (reviewer)
Branch:       agent/iap-001-orchestrator-bootstrap
Goal:         Produce a thorough read-only audit of the current InstaAutoPost
              pipeline before any implementation changes begin. The audit must
              surface: project structure, GitHub Actions workflows, Instagram
              publish flow, Supabase usage and schema assumptions,
              environment/secrets assumptions, dry-run/safe mode behavior, log
              and secret exposure risks, production publish risks, old naming
              drift, and the next safest implementation step. No code is changed.
              The only output is a completed audit entry in docs/AGENT_RUN_REPORT.md.

Scope:
  - Read-only inspection of local project files
  - Audit findings written to docs/AGENT_RUN_REPORT.md only
  - No code, workflow, Supabase, UI, or package file changes

Allowed files:
  - docs/AGENT_RUN_REPORT.md

Forbidden actions:
  - No publish, deploy, supabase_write, migration_apply
  - No secret_print, env_print, github_actions_run
  - No commit, push, merge
  - No write_app_code, write_workflow_code, write_supabase_code, write_ui_code
  - No install_packages

Validation commands:
  - python3 scripts/potucky_orchestrator.py status
  - python3 scripts/potucky_orchestrator.py doctor
  - python3 scripts/potucky_orchestrator.py print-next
  - git status --short

Expected result:
  - All validation commands exit 0
  - git status shows only docs/AGENT_RUN_REPORT.md as modified (untracked is OK)
  - docs/AGENT_RUN_REPORT.md contains a completed IAP-002 audit entry
  - No secrets appear in any output

Required run report:
  - File: docs/AGENT_RUN_REPORT.md
  - Fields: all — audit findings fill "What was done"

Codex review result:  pending
Final status:         pending
```

---

### IAP-001 — Orchestrator bootstrap and safety baseline

```
Task ID:      IAP-001
Title:        Orchestrator bootstrap and safety baseline
Status:       DONE
Owner Agent:  Claude Code
Branch:       agent/iap-001-orchestrator-bootstrap
Goal:         Bootstrap the POTUCKY ORCHESTRATOR workflow: implement the orchestrator
              script, task queue, prompt generation, auto mode, and supporting docs.
              Scope was expanded from read-only baseline because the bootstrap itself
              required creating orchestrator scripts and documentation.

Scope:
  - Implement scripts/potucky_orchestrator.py
  - Create scripts/potucky_agent_tasks.json
  - Create scripts/potucky_agent_prompts/
  - Create docs/POTUCKY_ORCHESTRATOR.md, AGENT_REVIEW_RULES.md, AGENT_TASK_QUEUE.md,
    AGENT_RUN_REPORT.md, PROJECT_STATUS.md, SECURITY_RULES.md
  - Update CLAUDE.md with orchestrator workflow rules

Allowed files:
  - scripts/potucky_orchestrator.py
  - scripts/potucky_agent_tasks.json
  - scripts/potucky_agent_prompts/
  - docs/AGENT_REVIEW_RULES.md
  - docs/AGENT_RUN_REPORT.md
  - docs/AGENT_TASK_QUEUE.md
  - docs/POTUCKY_ORCHESTRATOR.md
  - docs/PROJECT_STATUS.md
  - docs/SECURITY_RULES.md
  - CLAUDE.md

Forbidden actions:
  - No publish, deploy, supabase_write, migration_apply
  - No secret_print, env_print, github_actions_run
  - No commit, push, merge

Validation commands:
  - pwd
  - git status --short
  - git branch --show-current
  - git ls-files .github/workflows || true
  - find docs -maxdepth 2 -type f | sort || true

Expected result:
  - All validation commands exit 0
  - docs/AGENT_RUN_REPORT.md contains a completed report for IAP-001
  - No secrets appear in any output

Required run report:
  - File: docs/AGENT_RUN_REPORT.md
  - Fields: all

Codex review result:  PASS
Final status:         DONE — 2026-05-21, Codex PASS, mark-done run by user
```
