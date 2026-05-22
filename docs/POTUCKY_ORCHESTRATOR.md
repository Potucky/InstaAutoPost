# POTUCKY_ORCHESTRATOR.md

POTUCKY ORCHESTRATOR is the local agent command center for InstaAutoPost.
It coordinates the agent task queue, prepares Claude Code executor prompts,
prepares Codex read-only audit prompts, tracks task statuses, writes
orchestration entries to the run report, and prevents unsafe actions.

---

## What It Is

POTUCKY ORCHESTRATOR is a Python CLI script at `scripts/potucky_orchestrator.py`.
It reads the task queue from `scripts/potucky_agent_tasks.json` and operates on
the first active task.

It supports two modes:

- **Manual mode** — prepares prompt files; human pastes them into Claude Code and Codex.
- **Auto mode** — runs Claude Code and Codex CLI directly; bounded to one task, one execution, one review.

In both modes, `DONE` is never set automatically. The user must run `mark-done` intentionally.

---

## Core Principle

POTUCKY ORCHESTRATOR is powerful by design but conservative by default.

It coordinates work. It generates prompts. It updates task statuses.
It writes reports. It does not perform any risky production action
without explicit manual approval from the user.

Auto mode adds CLI execution capability while preserving all safety boundaries:
no publishing, no deploying, no migrations, no commits, no pushes.

---

## Task Status Flow

```text
TODO → IN_PROGRESS → NEEDS_REVIEW → NEEDS_USER_APPROVAL → DONE
              ↓             ↓
           NEEDS_FIX ←── NEEDS_FIX
              ↓
           BLOCKED (manual, any status)
```

| Status | Meaning |
| --- | --- |
| `TODO` | Not yet started. |
| `IN_PROGRESS` | Agent is working — Claude execution in progress or started. |
| `NEEDS_REVIEW` | Executor work done; Codex audit has not run yet. |
| `NEEDS_FIX` | Codex returned FAIL or execution errored; must be fixed before re-review. |
| `NEEDS_USER_APPROVAL` | Codex returned PASS; user must review output and run `mark-done`. |
| `DONE` | User confirmed complete after Codex PASS. Never set automatically. |
| `BLOCKED` | Cannot proceed — missing info, permission, or dependency. |

---

## Manual Mode

Manual mode prepares prompt files and prints instructions. Claude Code and Codex
are not invoked automatically.

### How to Prepare Prompts

```bash
python3 scripts/potucky_orchestrator.py prepare-prompts
```

Generates executor and Codex prompts for the first active task without
changing its status. Useful for inspecting prompts before starting.

### How to Run the Next Task (manual)

```bash
python3 scripts/potucky_orchestrator.py run-next
```

1. Finds the first `TODO` task.
2. Marks it `IN_PROGRESS`.
3. Generates executor and Codex prompt files.
4. Appends an orchestration entry to `docs/AGENT_RUN_REPORT.md`.
5. Prints exactly what to paste into Claude Code and Codex.

Claude Code and Codex are NOT invoked automatically.
The user must paste the prompts manually.

### How to Audit with Codex (manual)

After Claude Code finishes the executor work:

1. Open the Codex prompt file printed by `run-next` or `prepare-prompts`.
2. Copy the full contents.
3. Paste into Codex.
4. Codex returns `AUDIT_RESULT: PASS` or `AUDIT_RESULT: FAIL`.
5. If PASS: run `mark-done`.
6. If FAIL: run `mark-needs-fix`, fix the blockers, re-run `prepare-prompts`.

---

## Auto Mode

Auto mode invokes Claude Code and Codex CLI directly. It is bounded:
one task, one Claude execution, one Codex review. It stops and requires
manual action before advancing the queue.

### Safety Lock

Auto mode verifies before doing anything:

- The project root is exactly `/Users/vasylpopovich/Projects/InstaAutoPost`
- `scripts/potucky_agent_tasks.json` exists and is valid JSON
- The `tasks` key is present

If any check fails, auto mode refuses to run.

### doctor — Pre-flight check

```bash
python3 scripts/potucky_orchestrator.py doctor
```

Prints:

- Claude CLI availability
- Codex CLI availability
- git availability
- Current git branch and working tree summary
- Task file status (exists, valid JSON, task count)
- Prompt directory status
- Logs directory status
- Report file status
- Safety mode summary

Does not run agents. Safe to run any time.

### auto-execute TASK_ID — Run the Claude executor step

```bash
python3 scripts/potucky_orchestrator.py auto-execute IAP-001
```

1. Safety lock check.
2. Loads task; verifies status is `TODO`, `IN_PROGRESS`, or `NEEDS_FIX`.
3. Marks task `IN_PROGRESS`.
4. Generates a fresh Claude executor prompt.
5. If Claude CLI is not available: prints manual fallback instructions and exits.
6. Runs: `claude -p --output-format text` with the prompt file as stdin.
7. Streams stdout → `scripts/potucky_agent_prompts/logs/IAP-001_claude_stdout.log`
8. Streams stderr → `scripts/potucky_agent_prompts/logs/IAP-001_claude_stderr.log`
9. Exit code 0 → marks task `NEEDS_REVIEW`, appends report entry.
10. Exit code non-zero → marks task `NEEDS_FIX`, appends report entry.
11. Execution error → marks task `NEEDS_FIX`, appends report entry.

The orchestrator script itself does not print secrets, env vars, or tokens.
However, stdout and stderr from Claude and Codex are streamed as raw bytes directly
to log files in `scripts/potucky_agent_prompts/logs/`. The orchestrator does NOT
redact these logs. If Claude or Codex outputs secret values in their responses,
those values will appear in the log files. Treat log files as potentially sensitive;
do not share or commit them. No redaction is implemented — do not assume otherwise.

### auto-review TASK_ID — Run the Codex audit step

```bash
python3 scripts/potucky_orchestrator.py auto-review IAP-001
```

1. Safety lock check.
2. Loads task; verifies status is `NEEDS_REVIEW`.
3. Generates a fresh Codex review prompt.
4. If Codex CLI is not available: prints manual fallback instructions and exits.
5. Runs: `codex exec -s read-only --cd <project-root> -` with the prompt file as stdin.
6. Captures stdout for parsing; writes to `IAP-001_codex_stdout.log`.
7. Writes stderr to `IAP-001_codex_stderr.log`.
8. Parses output for the exact sentinel lines:
   - `AUDIT_RESULT: PASS` → marks task `NEEDS_USER_APPROVAL`
   - `AUDIT_RESULT: FAIL` → marks task `NEEDS_FIX`
   - Neither found → task remains `NEEDS_REVIEW`, reports unclear result
9. Appends report entry in all cases.

**Never marks DONE automatically.** A PASS moves to `NEEDS_USER_APPROVAL` — the user
must review the Codex output and run `mark-done` intentionally.

### auto-run-next — Full bounded autonomous cycle

```bash
python3 scripts/potucky_orchestrator.py auto-run-next
```

1. Safety lock check.
2. Finds the first `TODO` or `NEEDS_FIX` task.
3. Runs `auto-execute` for that task (one execution max).
4. If execute fails or exits non-zero, stops and reports.
5. If execute succeeds (task becomes `NEEDS_REVIEW`), runs `auto-review` (one review max).
6. Stops after review. Does not proceed to the next task. Does not mark DONE.

Max loop protection: one task, one Claude execution, one Codex review. No retries.
To retry, run the command again manually.

---

## Why DONE Is Always Manual

`DONE` is never set automatically, even after Codex returns PASS.

Reasons:

- Codex PASS means the audit found no blockers — it does not mean the work
  is acceptable to the user or meets product requirements.
- The user may want to inspect Claude's output and Codex's review before
  advancing the queue.
- Skipping human review on task completion would violate the principle that
  risky state transitions require explicit approval.

After `auto-review` sets `NEEDS_USER_APPROVAL`:

```bash
# Review Codex output first:
cat scripts/potucky_agent_prompts/logs/IAP-001_codex_stdout.log

# If satisfied, mark done:
python3 scripts/potucky_orchestrator.py mark-done IAP-001
```

---

## How It Uses Claude Code

For each task, POTUCKY ORCHESTRATOR generates a Claude Code executor prompt at:

```text
scripts/potucky_agent_prompts/<TASK-ID>_claude_executor_prompt.md
```

This prompt contains:

- The project path and task context
- Strict allowed files and forbidden actions
- Exact validation commands to run
- Report requirements for `docs/AGENT_RUN_REPORT.md`
- Stop conditions and final checklist

In manual mode: the user opens the file and pastes into Claude Code.
In auto mode: the orchestrator pipes it directly to `claude -p --output-format text`.

---

## How It Uses Codex

After executor work is complete, POTUCKY ORCHESTRATOR generates a Codex
read-only audit prompt at:

```text
scripts/potucky_agent_prompts/<TASK-ID>_codex_review_prompt.md
```

This prompt instructs Codex to:

- Inspect `git status` and `git diff`
- Verify only allowed files were changed
- Verify no forbidden actions were performed
- Check for secrets leakage
- Verify no publishing, deploy, migration, or GitHub Actions runs occurred
- Check the run report in `docs/AGENT_RUN_REPORT.md`
- Return exactly `AUDIT_RESULT: PASS` or `AUDIT_RESULT: FAIL`

In manual mode: the user pastes the prompt into Codex.
In auto mode: the orchestrator pipes it to `codex exec -s read-only --cd <root> -`.

Codex never writes files or code, never commits or deploys. In both modes, Codex
may only run the safe read-only inspection commands listed in the audit prompt.

---

## How to Add a Task

Edit `scripts/potucky_agent_tasks.json` and append a new object to the
`"tasks"` array following this structure:

```json
{
  "id": "IAP-002",
  "title": "Short task title",
  "status": "TODO",
  "branch": "agent/iap-002-slug",
  "mode": "read_only | code_change | doc_only",
  "priority": "high | medium | low",
  "allowed_files": [
    "path/to/file.py",
    "docs/AGENT_RUN_REPORT.md"
  ],
  "forbidden_actions": [
    "publish",
    "deploy",
    "commit",
    "push",
    "merge"
  ],
  "validation_commands": [
    "python3 -m py_compile scripts/some_file.py",
    "git status --short"
  ],
  "done_requires": [
    "executor_report",
    "codex_review_pass",
    "manual_approval_for_final_status"
  ],
  "notes": "Context for the agent working on this task."
}
```

POTUCKY ORCHESTRATOR always picks the first `TODO` task from the list,
so ordering matters. Also add the task to `docs/AGENT_TASK_QUEUE.md` in
the human-readable format for the full task record.

---

## How to Check Status

```bash
python3 scripts/potucky_orchestrator.py status
```

Prints current branch, working tree, first active task, task counts by status,
CLI availability for all 8 CLIs, prompt/logs/report paths, and safety mode.

---

## How to Mark Done, Blocked, or Needs-Fix

```bash
# Mark a task DONE (after Codex PASS and your manual review)
python3 scripts/potucky_orchestrator.py mark-done IAP-001

# Mark a task BLOCKED (missing info, permission, or dependency)
python3 scripts/potucky_orchestrator.py mark-blocked IAP-001

# Mark a task NEEDS_FIX (Codex returned FAIL, or manual fix needed)
python3 scripts/potucky_orchestrator.py mark-needs-fix IAP-001
```

Each command:

- Validates the task ID exists
- Validates the current status is a legal transition source
- Updates the status in `scripts/potucky_agent_tasks.json`
- Appends an orchestration entry to `docs/AGENT_RUN_REPORT.md`

`mark-done` is allowed **only from `NEEDS_USER_APPROVAL`**. This ensures DONE is
reached only after Codex returned PASS and the user explicitly approved. It is
never set automatically.

---

## How to See the Next Recommended Action

```bash
python3 scripts/potucky_orchestrator.py print-next
```

| Queue state | Recommendation |
| --- | --- |
| `TODO` | run `run-next` (manual) or `auto-run-next` (auto) |
| `IN_PROGRESS` | finish executor work, run `prepare-prompts` |
| `NEEDS_REVIEW` | run `auto-review <id>` or paste Codex prompt manually |
| `NEEDS_FIX` | run `auto-execute <id>` to retry or fix manually |
| `NEEDS_USER_APPROVAL` | review Codex output, run `mark-done <id>` |
| `BLOCKED` | resolve blocker manually |
| All `DONE` | add the next task |

---

## Manual Approvals Always Required

The following actions require explicit per-session user confirmation before
any agent, script, or workflow may proceed:

| Action | Approval requirement |
| --- | --- |
| Real Instagram publish | Explicit instruction in current session |
| Running publisher with `INSTAGRAM_API_ENABLED=true` | Explicit confirmation in current session |
| Applying Supabase migrations | Explicit confirmation before `supabase db push` |
| Destructive SQL | Explicit confirmation before execution |
| Enabling scheduled GitHub Actions cron | Explicit instruction in current session |
| Committing, pushing, or merging | Never done automatically |
| Deploying any service | Never done automatically |
| Marking a task DONE | Always requires `mark-done <id>` from the user |
| Changing secrets or env variable names | Explicit instruction required |

These are not overridden by task scope, urgency, or convenience.
See `docs/SECURITY_RULES.md` for the complete set of non-negotiable rules.

---

## Files

| File | Purpose |
| --- | --- |
| `scripts/potucky_orchestrator.py` | CLI orchestrator — the command center |
| `scripts/potucky_agent_tasks.json` | Machine-readable task queue |
| `scripts/potucky_agent_prompts/` | Generated executor and Codex prompts |
| `scripts/potucky_agent_prompts/logs/` | Claude and Codex execution logs |
| `docs/AGENT_TASK_QUEUE.md` | Human-readable task queue and workflow reference |
| `docs/AGENT_RUN_REPORT.md` | Run reports (executor + Codex + orchestrator entries) |
| `docs/AGENT_REVIEW_RULES.md` | Codex reviewer role and output format |
| `docs/SECURITY_RULES.md` | Non-negotiable security rules for all agents |
| `docs/PROJECT_STATUS.md` | Current project state snapshot |

---

## Command Reference

| Command | Args | Description |
| --- | --- | --- |
| `status` | — | Full status dashboard |
| `doctor` | — | Pre-flight check for auto mode |
| `prepare-prompts` | — | Generate prompt files (no status change) |
| `run-next` | — | Manual: mark first TODO IN_PROGRESS, print prompts |
| `auto-run-next` | — | Auto: execute + review first TODO or NEEDS_FIX task |
| `auto-execute` | `<id>` | Auto: run Claude executor step only |
| `auto-review` | `<id>` | Auto: run Codex review step only |
| `mark-done` | `<id>` | Mark task DONE (user only, never automatic) |
| `mark-blocked` | `<id>` | Mark task BLOCKED |
| `mark-needs-fix` | `<id>` | Mark task NEEDS_FIX |
| `print-next` | — | Print next recommended action |
