#!/usr/bin/env python3
"""POTUCKY ORCHESTRATOR — Local agent command center for InstaAutoPost."""

import json
import sys
import subprocess
import shutil
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EXPECTED_PROJECT_ROOT = Path("/Users/vasylpopovich/Projects/InstaAutoPost")
TASKS_FILE = Path(__file__).resolve().parent / "potucky_agent_tasks.json"
PROMPTS_DIR = Path(__file__).resolve().parent / "potucky_agent_prompts"
LOGS_DIR = PROMPTS_DIR / "logs"
REPORT_FILE = PROJECT_ROOT / "docs" / "AGENT_RUN_REPORT.md"

# Priority order for get_first_active_task (excludes NEEDS_USER_APPROVAL intentionally —
# that status waits for manual user approval, not more agent work)
ACTIVE_STATUSES_ORDERED = ["TODO", "IN_PROGRESS", "NEEDS_FIX", "NEEDS_REVIEW"]

# print-next also surfaces NEEDS_USER_APPROVAL so the user knows to run mark-done
PRINT_NEXT_STATUSES = ["TODO", "IN_PROGRESS", "NEEDS_FIX", "NEEDS_REVIEW", "NEEDS_USER_APPROVAL"]

VALID_TRANSITIONS = {
    # mark-done is restricted to NEEDS_USER_APPROVAL only — ensures Codex PASS happened first.
    "mark-done": {"NEEDS_USER_APPROVAL"},
    "mark-blocked": {"TODO", "IN_PROGRESS", "NEEDS_FIX", "NEEDS_REVIEW", "NEEDS_USER_APPROVAL"},
    "mark-needs-fix": {"NEEDS_REVIEW", "IN_PROGRESS", "NEEDS_USER_APPROVAL"},
}

CLAUDE_TIMEOUT = 600   # seconds
CODEX_TIMEOUT = 300    # seconds


# ---------------------------------------------------------------------------
# Task file helpers
# ---------------------------------------------------------------------------

def load_tasks():
    if not TASKS_FILE.exists():
        print(f"ERROR: Task file not found: {TASKS_FILE}")
        sys.exit(1)
    with TASKS_FILE.open() as f:
        return json.load(f)


def save_tasks(data):
    with TASKS_FILE.open("w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def get_first_active_task(tasks):
    for status in ACTIVE_STATUSES_ORDERED:
        for task in tasks:
            if task.get("status") == status:
                return task
    return None


def find_task_by_id(tasks, task_id):
    for task in tasks:
        if task.get("id") == task_id:
            return task
    return None


def counts_by_status(tasks):
    counts = {}
    for task in tasks:
        s = task.get("status", "UNKNOWN")
        counts[s] = counts.get(s, 0) + 1
    return counts


def get_blocking_task(tasks, except_id=None):
    """Return the first task in a blocking state, excluding except_id."""
    blocking = {"IN_PROGRESS", "NEEDS_REVIEW", "NEEDS_FIX", "NEEDS_USER_APPROVAL"}
    for task in tasks:
        if task.get("id") == except_id:
            continue
        if task.get("status") in blocking:
            return task
    return None


# ---------------------------------------------------------------------------
# CLI and git helpers
# ---------------------------------------------------------------------------

def check_cli(name):
    return shutil.which(name) is not None


def run_subprocess(args):
    """Run a subprocess without shell=True. Returns (stdout, returncode)."""
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=10)
        return result.stdout.strip(), result.returncode
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return "", 1


def get_git_branch():
    out, rc = run_subprocess(["git", "-C", str(PROJECT_ROOT), "branch", "--show-current"])
    return out if rc == 0 else "unknown"


def get_git_status_summary():
    out, rc = run_subprocess(["git", "-C", str(PROJECT_ROOT), "status", "--short"])
    if rc != 0:
        return "git status unavailable"
    if not out:
        return "clean working tree"
    lines = out.splitlines()
    return f"{len(lines)} file(s) modified/untracked"


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


# ---------------------------------------------------------------------------
# Safety lock
# ---------------------------------------------------------------------------

def safety_lock_check():
    """Verify we are operating inside the correct project root before auto mode."""
    if PROJECT_ROOT.resolve() != EXPECTED_PROJECT_ROOT.resolve():
        print("SAFETY LOCK FAILED: Project root mismatch.")
        print(f"  Expected: {EXPECTED_PROJECT_ROOT}")
        print(f"  Got:      {PROJECT_ROOT}")
        print("  Auto mode is disabled outside InstaAutoPost.")
        return False
    if not TASKS_FILE.exists():
        print(f"SAFETY LOCK FAILED: Task file not found: {TASKS_FILE}")
        return False
    try:
        data = json.loads(TASKS_FILE.read_text())
        if "tasks" not in data:
            print("SAFETY LOCK FAILED: Task file missing 'tasks' key.")
            return False
    except json.JSONDecodeError as e:
        print(f"SAFETY LOCK FAILED: Task file invalid JSON: {e}")
        return False
    return True


# ---------------------------------------------------------------------------
# Report helper
# ---------------------------------------------------------------------------

def append_report(task_id, task_title, action, details):
    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    entry = (
        "\n---\n"
        f"POTUCKY ORCHESTRATOR entry\n"
        f"Task ID:  {task_id}\n"
        f"Title:    {task_title}\n"
        f"Action:   {action}\n"
        f"Date:     {now_iso()}\n"
        f"Details:  {details}\n"
        "---\n"
    )
    with REPORT_FILE.open("a") as f:
        f.write(entry)
    print(f"  Appended orchestration entry to: {REPORT_FILE}")


# ---------------------------------------------------------------------------
# Prompt generators
# ---------------------------------------------------------------------------

def generate_executor_prompt(task):
    task_id = task["id"]
    title = task["title"]
    status = task["status"]
    branch = task.get("branch", "N/A")
    allowed_files = "\n".join(f"  - {f}" for f in task.get("allowed_files", []))
    forbidden = "\n".join(f"  - {a}" for a in task.get("forbidden_actions", []))
    validation = "\n".join(f"  - {c}" for c in task.get("validation_commands", []))
    notes = task.get("notes", "None.")

    return f"""# POTUCKY ORCHESTRATOR — Claude Code Executor Prompt
# Generated: {now_iso()}
# Orchestrator: POTUCKY ORCHESTRATOR v0.1.0

## PROJECT
Path: {PROJECT_ROOT}

## TASK
ID:     {task_id}
Title:  {title}
Status: {status}
Branch: {branch}

## STRICT SCOPE
You are operating under POTUCKY ORCHESTRATOR safety rules.
Work ONLY within the declared allowed files below.
Do NOT modify any file outside this list.

## ALLOWED FILES
{allowed_files if allowed_files.strip() else "  (see task definition)"}

## FORBIDDEN ACTIONS
The following actions are STRICTLY PROHIBITED for this task:
{forbidden if forbidden.strip() else "  (see task definition)"}

Additionally, at all times:
  - Do NOT publish to Instagram or any social platform
  - Do NOT deploy any service
  - Do NOT apply Supabase migrations
  - Do NOT run destructive SQL (DROP, TRUNCATE, DELETE without WHERE)
  - Do NOT print or log secrets, tokens, or environment variable values
  - Do NOT run GitHub Actions workflows
  - Do NOT commit
  - Do NOT push
  - Do NOT merge
  - Do NOT install packages
  - Do NOT perform broad refactors outside task scope
  - Do NOT assume approval for any risky action — ask first

## VALIDATION COMMANDS
Run these exactly to verify the task is complete:
{validation if validation.strip() else "  (see task definition)"}

All validation commands must exit 0.
No secrets must appear in any output.

## REPORT REQUIREMENT
Before requesting Codex review, write a completed report entry to:
  docs/AGENT_RUN_REPORT.md

Use the exact template from that file. Fill every field.
Write "none" or "N/A" where not applicable — do not leave fields blank.

## STOP CONDITIONS
Stop and ask the user if you encounter any of the following:
  - An action on the FORBIDDEN ACTIONS list
  - A validation command that exits non-zero
  - Any uncertainty about whether an action is safe
  - Any command that would read, write, or expose secrets
  - Any command that would trigger network calls beyond safe read-only inspection

## NOTES
{notes}

## FINAL CHECKLIST (required before requesting Codex review)
  [ ] All validation commands passed (exit 0)
  [ ] No secrets appear in any output
  [ ] Only allowed files were modified
  [ ] Report written to docs/AGENT_RUN_REPORT.md
  [ ] No commits made
  [ ] No pushes made
  [ ] No deploys triggered
  [ ] No Instagram/TikTok API calls made
  [ ] No Supabase migrations applied
"""


def generate_codex_prompt(task):
    task_id = task["id"]
    title = task["title"]
    allowed_files = task.get("allowed_files", [])
    forbidden = task.get("forbidden_actions", [])

    allowed_list = "\n".join(f"  - {f}" for f in allowed_files)
    forbidden_list = "\n".join(f"  - {a}" for a in forbidden)

    return f"""# POTUCKY ORCHESTRATOR — Codex Read-Only Audit Prompt
# Generated: {now_iso()}
# Orchestrator: POTUCKY ORCHESTRATOR v0.1.0

## ROLE
You are Codex, operating as a read-only auditor.
You MUST NOT modify files.
You MUST NOT write files.
You MUST NOT commit.
You MUST NOT push.
You MUST NOT deploy.
You MUST NOT publish.
You MUST NOT apply migrations.
You MUST NOT print secrets or env vars.

You MAY run safe read-only inspection commands to gather the evidence you need.
You READ completed work and return a structured audit verdict.

## ALLOWED READ-ONLY COMMANDS
You MAY run the following read-only inspection commands:
  - pwd
  - git status --short
  - git branch --show-current
  - git diff HEAD
  - git diff --stat HEAD
  - git ls-files
  - find docs -maxdepth 2 -type f | sort
  - sed / cat / head / tail  (project files only — never .env or secrets files)
  - grep / ripgrep           (project files only — never .env or secrets files)

## FORBIDDEN COMMANDS
You MUST NOT run any of the following:
  - git commit
  - git push
  - git merge
  - gh workflow run
  - supabase db push
  - supabase migration up
  - supabase secrets list
  - env
  - printenv
  - cat .env  (or any secrets / credential file)
  - npm install
  - Any destructive SQL (DROP, TRUNCATE, DELETE without WHERE)
  - Any publish, deploy, or external API call

## TASK UNDER REVIEW
ID:     {task_id}
Title:  {title}

## AUDIT STEPS

1. Run: git status --short
   Verify: only files in the ALLOWED FILES list appear as modified or added.

2. Run: git diff HEAD
   Check all changes for forbidden patterns, scope violations, and secret leakage.

3. For each changed file:
   - Is it in the ALLOWED FILES list?
   - Does it contain hardcoded secrets, tokens, or credentials?
   - Does it introduce code paths that could trigger publishing, deploying, or migrations?

4. Read docs/AGENT_RUN_REPORT.md (use cat or head):
   - Is there a completed report entry for {task_id}?
   - Are all fields filled? (no blanks — "none" or "N/A" is acceptable)
   - Does the report accurately reflect what was done?

## ALLOWED FILES FOR THIS TASK
{allowed_list if allowed_list.strip() else "  (inspect task definition)"}

## FORBIDDEN ACTIONS TO VERIFY
These must NOT have been performed:
{forbidden_list if forbidden_list.strip() else "  (inspect task definition)"}

Additionally verify that none of the following occurred:
  - Instagram or TikTok API calls
  - Real publish triggered
  - Supabase migration applied
  - GitHub Actions workflow run triggered
  - Destructive SQL executed (DROP, TRUNCATE, DELETE without WHERE)
  - Secrets, tokens, or env var values printed or logged
  - Commits made
  - Pushes made
  - Merges performed
  - Packages installed

## SECURITY CHECKS
  - No hardcoded IG_ACCESS_TOKEN, SUPABASE_SERVICE_ROLE_KEY, refresh tokens, or API keys
  - No signed URL query parameters exposed in logs or code
  - No command injection patterns (user input passed to shell unescaped)
  - No SQL injection patterns
  - No XSS patterns in UI code
  - No open redirect patterns

## REQUIRED OUTPUT FORMAT

Return your verdict in EXACTLY this format:

```
Codex Review — Task ID: {task_id}
Result: PASS | FAIL

Blockers:
  - <description>  [file: <path>, line: <N> if known]
  (write "none" if no blockers)

Non-blocking suggestions:
  - <description>  [file: <path>, line: <N> if known]
  (write "none" if no suggestions)

Files reviewed:
  - <path>

Final recommendation:
  <One paragraph. If PASS: confirm the task is safe to mark DONE.
   If FAIL: describe what must be fixed before re-review.>
```

End your response with exactly one of:
  AUDIT_RESULT: PASS
or
  AUDIT_RESULT: FAIL

## PASS / FAIL RULE
PASS requires zero blockers across all check areas.
FAIL if any single blocker exists.
Suggestions are non-blocking and do not prevent PASS.
Return FAIL with blocker "run report or changed files not available for review" ONLY if
the required files and git state are genuinely inaccessible after attempting the allowed
read-only inspection commands above.
"""


def write_prompts(task):
    PROMPTS_DIR.mkdir(parents=True, exist_ok=True)
    task_id = task["id"]
    executor_file = PROMPTS_DIR / f"{task_id}_claude_executor_prompt.md"
    codex_file = PROMPTS_DIR / f"{task_id}_codex_review_prompt.md"
    executor_file.write_text(generate_executor_prompt(task))
    codex_file.write_text(generate_codex_prompt(task))
    return executor_file, codex_file


# ---------------------------------------------------------------------------
# Auto execution helpers
# ---------------------------------------------------------------------------

def ensure_logs_dir():
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    return LOGS_DIR


def run_claude_executor(task, prompt_file):
    """
    Run Claude CLI in non-interactive print mode.
    Streams stdout/stderr directly to log files — never to terminal.
    Returns (returncode, error_msg). returncode is None on execution error.
    """
    task_id = task["id"]
    logs_dir = ensure_logs_dir()
    stdout_log = logs_dir / f"{task_id}_claude_stdout.log"
    stderr_log = logs_dir / f"{task_id}_claude_stderr.log"

    cmd = ["claude", "-p", "--output-format", "text"]

    print(f"  Command:    claude -p --output-format text  (stdin < prompt file)")
    print(f"  stdout log: {stdout_log}")
    print(f"  stderr log: {stderr_log}")
    print(f"  Timeout:    {CLAUDE_TIMEOUT}s")

    try:
        with (
            prompt_file.open("rb") as stdin_f,
            stdout_log.open("wb") as stdout_f,
            stderr_log.open("wb") as stderr_f,
        ):
            result = subprocess.run(
                cmd,
                stdin=stdin_f,
                stdout=stdout_f,
                stderr=stderr_f,
                timeout=CLAUDE_TIMEOUT,
                cwd=str(PROJECT_ROOT),
            )
        return result.returncode, None
    except subprocess.TimeoutExpired:
        return None, f"Claude timed out after {CLAUDE_TIMEOUT}s"
    except FileNotFoundError:
        return None, "claude not found in PATH"
    except Exception as e:
        return None, f"Claude error: {type(e).__name__}: {e}"


def run_codex_review(task, prompt_file):
    """
    Run Codex exec in read-only sandbox mode.
    Captures stdout to memory for AUDIT_RESULT parsing, then writes to log.
    Returns (returncode, stdout_text, error_msg).
    """
    task_id = task["id"]
    logs_dir = ensure_logs_dir()
    stdout_log = logs_dir / f"{task_id}_codex_stdout.log"
    stderr_log = logs_dir / f"{task_id}_codex_stderr.log"

    # `-` tells codex exec to read the prompt from stdin
    cmd = ["codex", "exec", "-s", "read-only", "--cd", str(PROJECT_ROOT), "-"]

    print(f"  Command:    codex exec -s read-only --cd {PROJECT_ROOT}  (stdin < prompt file)")
    print(f"  stdout log: {stdout_log}")
    print(f"  stderr log: {stderr_log}")
    print(f"  Timeout:    {CODEX_TIMEOUT}s")

    try:
        with prompt_file.open("rb") as stdin_f:
            result = subprocess.run(
                cmd,
                stdin=stdin_f,
                capture_output=True,
                timeout=CODEX_TIMEOUT,
                cwd=str(PROJECT_ROOT),
            )
        stdout_text = result.stdout.decode("utf-8", errors="replace")
        stderr_text = result.stderr.decode("utf-8", errors="replace")
        stdout_log.write_text(stdout_text)
        stderr_log.write_text(stderr_text)
        return result.returncode, stdout_text, None
    except subprocess.TimeoutExpired:
        return None, "", f"Codex timed out after {CODEX_TIMEOUT}s"
    except FileNotFoundError:
        return None, "", "codex not found in PATH"
    except Exception as e:
        return None, "", f"Codex error: {type(e).__name__}: {e}"


def parse_audit_result(output):
    """Return 'PASS', 'FAIL', or None by scanning for the exact sentinel lines."""
    for line in output.splitlines():
        stripped = line.strip()
        if stripped == "AUDIT_RESULT: PASS":
            return "PASS"
        if stripped == "AUDIT_RESULT: FAIL":
            return "FAIL"
    return None


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_status():
    data = load_tasks()
    tasks = data.get("tasks", [])
    active = get_first_active_task(tasks)
    counts = counts_by_status(tasks)
    branch = get_git_branch()
    git_summary = get_git_status_summary()

    clis = ["claude", "codex", "gh", "supabase", "git", "python3", "node", "npm"]
    cli_status = {c: ("available" if check_cli(c) else "NOT FOUND") for c in clis}

    print("=" * 62)
    print("  POTUCKY ORCHESTRATOR")
    print(f"  Version: {data.get('version', '?')}")
    print("=" * 62)
    print(f"\n  Branch:        {branch}")
    print(f"  Working tree:  {git_summary}")
    print()

    if active:
        print("  First active task:")
        print(f"    ID:     {active['id']}")
        print(f"    Title:  {active['title']}")
        print(f"    Status: {active['status']}")
    else:
        # Check for NEEDS_USER_APPROVAL separately
        nua = next((t for t in tasks if t.get("status") == "NEEDS_USER_APPROVAL"), None)
        if nua:
            print("  Awaiting user approval:")
            print(f"    ID:     {nua['id']}")
            print(f"    Title:  {nua['title']}")
            print(f"    Status: NEEDS_USER_APPROVAL")
        else:
            print("  No active tasks.")

    print()
    print("  Task counts:")
    for status, count in sorted(counts.items()):
        print(f"    {status:<22} {count}")

    print()
    print("  CLI availability:")
    for cli, avail in cli_status.items():
        print(f"    {cli:<14} {avail}")

    print()
    print(f"  Prompt directory: {PROMPTS_DIR}")
    print(f"  Logs directory:   {LOGS_DIR}")
    print(f"  Report file:      {REPORT_FILE}")
    print()
    print("  SAFETY MODE: SAFE BY DEFAULT")
    print("  Approval required for: " + ", ".join(data.get("approval_required_for", [])))
    print("=" * 62)


def cmd_doctor():
    print("=" * 62)
    print("  POTUCKY ORCHESTRATOR — doctor")
    print("=" * 62)
    print()

    clis = ["claude", "codex", "git"]
    print("  CLI availability:")
    for cli in clis:
        avail = "OK" if check_cli(cli) else "NOT FOUND"
        print(f"    {cli:<14} {avail}")
    print()

    branch = get_git_branch()
    git_summary = get_git_status_summary()
    print(f"  Git branch:      {branch}")
    print(f"  Working tree:    {git_summary}")
    print()

    print("  Task file:")
    if TASKS_FILE.exists():
        try:
            data = json.loads(TASKS_FILE.read_text())
            tasks = data.get("tasks", [])
            print(f"    {TASKS_FILE}")
            print(f"    Status: OK — {len(tasks)} task(s)")
        except json.JSONDecodeError as e:
            print(f"    {TASKS_FILE}")
            print(f"    Status: INVALID JSON — {e}")
    else:
        print(f"    {TASKS_FILE}")
        print(f"    Status: MISSING")
    print()

    print("  Prompt directory:")
    if PROMPTS_DIR.exists():
        count = len(list(PROMPTS_DIR.glob("*.md")))
        print(f"    {PROMPTS_DIR}")
        print(f"    Status: OK — {count} prompt file(s)")
    else:
        print(f"    {PROMPTS_DIR}")
        print(f"    Status: MISSING — will be created on first use")
    print()

    print("  Logs directory:")
    if LOGS_DIR.exists():
        count = len(list(LOGS_DIR.glob("*.log")))
        print(f"    {LOGS_DIR}")
        print(f"    Status: OK — {count} log file(s)")
    else:
        print(f"    {LOGS_DIR}")
        print(f"    Status: MISSING — will be created on first auto run")
    print()

    print("  Report file:")
    if REPORT_FILE.exists():
        print(f"    {REPORT_FILE}")
        print(f"    Status: OK")
    else:
        print(f"    {REPORT_FILE}")
        print(f"    Status: MISSING")
    print()

    print("  Safety mode:     SAFE BY DEFAULT")
    print("  Auto mode:       bounded — one task, one Claude run, one Codex run")
    print("  DONE requires:   explicit user command (never automatic)")
    print("  Auto mode lock:  project root must be", EXPECTED_PROJECT_ROOT)
    print()
    print("=" * 62)


def cmd_prepare_prompts():
    data = load_tasks()
    tasks = data.get("tasks", [])
    task = get_first_active_task(tasks)
    if not task:
        print("No active task found (TODO, IN_PROGRESS, NEEDS_FIX, NEEDS_REVIEW).")
        return

    executor_file, codex_file = write_prompts(task)

    print(f"\nPOTUCKY ORCHESTRATOR — Prompts prepared for {task['id']}")
    print(f"  Executor prompt: {executor_file}")
    print(f"  Codex prompt:    {codex_file}")
    print()
    print("Next manual steps:")
    print(f"  1. Open: {executor_file}")
    print(f"     Copy the full contents into Claude Code and run the task.")
    print(f"  2. After executor work is complete, open: {codex_file}")
    print(f"     Copy the full contents into Codex for the read-only audit.")
    print(f"  3. After Codex returns AUDIT_RESULT: PASS, run:")
    print(f"     python3 scripts/potucky_orchestrator.py mark-done {task['id']}")
    print()
    print("Task status was NOT changed by prepare-prompts.")


def cmd_run_next():
    data = load_tasks()
    tasks = data.get("tasks", [])
    blocker = get_blocking_task(tasks)
    if blocker:
        print(f"ERROR: Cannot start a new task — '{blocker['id']}' is {blocker['status']}.")
        print(f"  Resolve task {blocker['id']} first, then retry.")
        sys.exit(1)

    task = next((t for t in tasks if t.get("status") == "TODO"), None)
    if not task:
        print("No TODO task found.")
        print("Run: python3 scripts/potucky_orchestrator.py print-next")
        return

    task["status"] = "IN_PROGRESS"
    save_tasks(data)

    executor_file, codex_file = write_prompts(task)
    append_report(
        task["id"],
        task["title"],
        "IN_PROGRESS — run-next called",
        "Task marked IN_PROGRESS. Executor and Codex prompts generated. "
        "Manual execution required — no automated run performed.",
    )

    print(f"\nPOTUCKY ORCHESTRATOR — run-next")
    print(f"  Task {task['id']} marked IN_PROGRESS.")
    print(f"  Executor prompt: {executor_file}")
    print(f"  Codex prompt:    {codex_file}")
    print()
    print("STEP 1 — Paste into Claude Code:")
    print("-" * 58)
    print(f"  File: {executor_file}")
    print(f"  Copy the full contents and paste into Claude Code.")
    print("-" * 58)
    print()
    print("STEP 2 — After Claude Code finishes, paste into Codex:")
    print("-" * 58)
    print(f"  File: {codex_file}")
    print(f"  Copy the full contents and paste into Codex.")
    print("-" * 58)
    print()
    print("STEP 3 — After Codex returns AUDIT_RESULT: PASS, run:")
    print(f"  python3 scripts/potucky_orchestrator.py mark-done {task['id']}")
    print()
    print("NOTE: No automated execution was performed.")
    print("      Claude Code and Codex must be run manually.")
    print("      Or use: python3 scripts/potucky_orchestrator.py auto-run-next")


def cmd_auto_execute(task_id):
    if not safety_lock_check():
        sys.exit(1)

    data = load_tasks()
    tasks = data.get("tasks", [])
    task = find_task_by_id(tasks, task_id)
    if not task:
        print(f"ERROR: Task {task_id} not found.")
        sys.exit(1)

    allowed_from = {"TODO", "IN_PROGRESS", "NEEDS_FIX"}
    current_status = task.get("status", "")
    if current_status not in allowed_from:
        print(f"ERROR: auto-execute not allowed from status '{current_status}'.")
        print(f"  Allowed from: {', '.join(sorted(allowed_from))}")
        sys.exit(1)

    if current_status in {"TODO", "NEEDS_FIX"}:
        blocker = get_blocking_task(tasks, except_id=task_id)
        if blocker:
            print(f"ERROR: Cannot start task {task_id} — '{blocker['id']}' is {blocker['status']}.")
            print(f"  Resolve task {blocker['id']} first, then retry.")
            sys.exit(1)

    print(f"\nPOTUCKY ORCHESTRATOR — auto-execute {task_id}")
    print(f"  Task:   {task['title']}")
    print(f"  Status: {current_status} → IN_PROGRESS")
    print()

    task["status"] = "IN_PROGRESS"
    save_tasks(data)

    executor_file, _ = write_prompts(task)
    print(f"  Executor prompt: {executor_file}")
    print()

    if not check_cli("claude"):
        print("  FALLBACK: Claude CLI not available.")
        print(f"  Manual step: open {executor_file}")
        print("               Copy the full contents and paste into Claude Code.")
        append_report(
            task_id,
            task["title"],
            "IN_PROGRESS — auto-execute: Claude CLI not available, manual fallback",
            "Claude CLI not found in PATH. Executor prompt generated. Manual paste required.",
        )
        return

    returncode, error = run_claude_executor(task, executor_file)

    if error:
        print(f"  ERROR: {error}")
        task["status"] = "NEEDS_FIX"
        save_tasks(data)
        append_report(
            task_id,
            task["title"],
            "NEEDS_FIX — auto-execute: Claude execution error",
            f"Claude execution error: {error}. Check logs: {LOGS_DIR}.",
        )
        print(f"  Task {task_id} marked NEEDS_FIX.")
        return

    print(f"  Claude exit code: {returncode}")

    if returncode == 0:
        task["status"] = "NEEDS_REVIEW"
        save_tasks(data)
        append_report(
            task_id,
            task["title"],
            "NEEDS_REVIEW — auto-execute: Claude exited 0",
            f"Claude executor exited 0. Task moved to NEEDS_REVIEW. "
            f"Logs: {LOGS_DIR}.",
        )
        print(f"  Task {task_id} marked NEEDS_REVIEW.")
        print(f"  Next: python3 scripts/potucky_orchestrator.py auto-review {task_id}")
    else:
        task["status"] = "NEEDS_FIX"
        save_tasks(data)
        append_report(
            task_id,
            task["title"],
            f"NEEDS_FIX — auto-execute: Claude exited {returncode}",
            f"Claude executor exited non-zero ({returncode}). Task moved to NEEDS_FIX. "
            f"Check logs: {LOGS_DIR}.",
        )
        print(f"  Task {task_id} marked NEEDS_FIX.")
        print(f"  Check logs: {LOGS_DIR}")
        print(f"  stdout: {LOGS_DIR}/{task_id}_claude_stdout.log")
        print(f"  stderr: {LOGS_DIR}/{task_id}_claude_stderr.log")


def cmd_auto_review(task_id):
    if not safety_lock_check():
        sys.exit(1)

    data = load_tasks()
    tasks = data.get("tasks", [])
    task = find_task_by_id(tasks, task_id)
    if not task:
        print(f"ERROR: Task {task_id} not found.")
        sys.exit(1)

    current_status = task.get("status", "")
    if current_status != "NEEDS_REVIEW":
        print(f"ERROR: auto-review only allowed from NEEDS_REVIEW (current: '{current_status}').")
        sys.exit(1)

    print(f"\nPOTUCKY ORCHESTRATOR — auto-review {task_id}")
    print(f"  Task: {task['title']}")
    print()

    _, codex_file = write_prompts(task)
    print(f"  Codex prompt: {codex_file}")
    print()

    if not check_cli("codex"):
        print("  FALLBACK: Codex CLI not available.")
        print(f"  Manual step: open {codex_file}")
        print("               Copy the full contents and paste into Codex.")
        append_report(
            task_id,
            task["title"],
            "NEEDS_REVIEW — auto-review: Codex CLI not available, manual fallback",
            "Codex CLI not found in PATH. Review prompt generated. Manual paste required.",
        )
        return

    returncode, stdout_text, error = run_codex_review(task, codex_file)

    if error:
        print(f"  ERROR: {error}")
        append_report(
            task_id,
            task["title"],
            "NEEDS_REVIEW — auto-review: Codex execution error",
            f"Codex execution error: {error}. Task remains NEEDS_REVIEW.",
        )
        print(f"  Task {task_id} remains NEEDS_REVIEW.")
        return

    print(f"  Codex exit code: {returncode}")

    audit_result = parse_audit_result(stdout_text)
    print(f"  Audit result parsed: {audit_result or 'NOT FOUND in output'}")

    if audit_result == "PASS":
        task["status"] = "NEEDS_USER_APPROVAL"
        save_tasks(data)
        append_report(
            task_id,
            task["title"],
            "NEEDS_USER_APPROVAL — auto-review: Codex PASS",
            "Codex returned AUDIT_RESULT: PASS. Task moved to NEEDS_USER_APPROVAL. "
            "DONE requires explicit user command. "
            f"Codex output: {LOGS_DIR}/{task_id}_codex_stdout.log",
        )
        print(f"  Task {task_id} marked NEEDS_USER_APPROVAL.")
        print()
        print("  Codex returned PASS. Review the audit output before marking DONE.")
        print(f"  Codex output: {LOGS_DIR}/{task_id}_codex_stdout.log")
        print(f"  To mark DONE: python3 scripts/potucky_orchestrator.py mark-done {task_id}")

    elif audit_result == "FAIL":
        task["status"] = "NEEDS_FIX"
        save_tasks(data)
        append_report(
            task_id,
            task["title"],
            "NEEDS_FIX — auto-review: Codex FAIL",
            "Codex returned AUDIT_RESULT: FAIL. Task moved to NEEDS_FIX. "
            f"Review blockers: {LOGS_DIR}/{task_id}_codex_stdout.log",
        )
        print(f"  Task {task_id} marked NEEDS_FIX.")
        print(f"  Codex blockers: {LOGS_DIR}/{task_id}_codex_stdout.log")
        print(f"  Fix blockers, then: python3 scripts/potucky_orchestrator.py auto-execute {task_id}")

    else:
        append_report(
            task_id,
            task["title"],
            "NEEDS_REVIEW — auto-review: unclear audit result",
            "Codex output did not contain AUDIT_RESULT: PASS or AUDIT_RESULT: FAIL. "
            f"Task remains NEEDS_REVIEW. Review: {LOGS_DIR}/{task_id}_codex_stdout.log",
        )
        print(f"  Task {task_id} remains NEEDS_REVIEW (unclear audit result).")
        print(f"  Codex output: {LOGS_DIR}/{task_id}_codex_stdout.log")
        print("  Possible causes: Codex did not emit the required sentinel line,")
        print("                   or the prompt format was not followed.")


def cmd_auto_run_next():
    if not safety_lock_check():
        sys.exit(1)

    data = load_tasks()
    tasks = data.get("tasks", [])

    task = next(
        (t for t in tasks if t.get("status") in {"TODO", "NEEDS_FIX"}),
        None,
    )
    if not task:
        print("No TODO or NEEDS_FIX task found.")
        print("Run: python3 scripts/potucky_orchestrator.py print-next")
        return

    task_id = task["id"]
    blocker = get_blocking_task(tasks, except_id=task_id)
    if blocker:
        print(f"ERROR: Cannot proceed — '{blocker['id']}' is {blocker['status']}.")
        print(f"  Resolve task {blocker['id']} first, then retry.")
        sys.exit(1)

    print(f"\nPOTUCKY ORCHESTRATOR — auto-run-next")
    print(f"  Target:  {task_id} — {task['title']}  [{task['status']}]")
    print(f"  Cycle:   execute once → review once → stop")
    print(f"  DONE:    requires explicit user command after review")
    print()

    # Step 1: execute (one run max)
    cmd_auto_execute(task_id)

    # Re-read to check status after execute
    data = load_tasks()
    tasks = data.get("tasks", [])
    task = find_task_by_id(tasks, task_id)
    if not task or task.get("status") != "NEEDS_REVIEW":
        current = task.get("status", "unknown") if task else "unknown"
        print(f"\nauto-run-next: stopping after execute (task status: {current}).")
        print("  Resolve any issues, then re-run auto-run-next or use manual steps.")
        return

    # Step 2: review (one run max)
    print()
    cmd_auto_review(task_id)

    print()
    print("=" * 58)
    print("  auto-run-next complete.")
    print("  One task. One Claude execution. One Codex review.")
    print("  DONE requires your explicit command.")
    print("=" * 58)


def cmd_mark_done(task_id):
    data = load_tasks()
    tasks = data.get("tasks", [])
    task = find_task_by_id(tasks, task_id)
    if not task:
        print(f"ERROR: Task {task_id} not found.")
        sys.exit(1)
    allowed_from = VALID_TRANSITIONS["mark-done"]
    if task["status"] not in allowed_from:
        print(f"ERROR: Cannot mark DONE from status '{task['status']}'.")
        print(f"  Allowed from: {', '.join(sorted(allowed_from))}")
        sys.exit(1)
    task["status"] = "DONE"
    save_tasks(data)
    append_report(
        task_id,
        task["title"],
        "DONE — mark-done called by user",
        "Task manually marked DONE. Implies: executor work complete, "
        "validation passed, run report filed, Codex PASS received.",
    )
    print(f"Task {task_id} marked DONE.")


def cmd_mark_blocked(task_id):
    data = load_tasks()
    tasks = data.get("tasks", [])
    task = find_task_by_id(tasks, task_id)
    if not task:
        print(f"ERROR: Task {task_id} not found.")
        sys.exit(1)
    allowed_from = VALID_TRANSITIONS["mark-blocked"]
    if task["status"] not in allowed_from:
        print(f"ERROR: Cannot mark BLOCKED from status '{task['status']}'.")
        print(f"  Allowed from: {', '.join(sorted(allowed_from))}")
        sys.exit(1)
    task["status"] = "BLOCKED"
    save_tasks(data)
    append_report(
        task_id,
        task["title"],
        "BLOCKED — mark-blocked called by user",
        "Task manually marked BLOCKED. User must resolve blocker before proceeding.",
    )
    print(f"Task {task_id} marked BLOCKED.")
    print("Document the blocker in docs/AGENT_TASK_QUEUE.md or docs/AGENT_RUN_REPORT.md.")


def cmd_mark_needs_fix(task_id):
    data = load_tasks()
    tasks = data.get("tasks", [])
    task = find_task_by_id(tasks, task_id)
    if not task:
        print(f"ERROR: Task {task_id} not found.")
        sys.exit(1)
    allowed_from = VALID_TRANSITIONS["mark-needs-fix"]
    if task["status"] not in allowed_from:
        print(f"ERROR: Cannot mark NEEDS_FIX from status '{task['status']}'.")
        print(f"  Allowed from: {', '.join(sorted(allowed_from))}")
        sys.exit(1)
    task["status"] = "NEEDS_FIX"
    save_tasks(data)
    append_report(
        task_id,
        task["title"],
        "NEEDS_FIX — mark-needs-fix called by user",
        "Task marked NEEDS_FIX. Codex returned FAIL or fix required. "
        "Return to Claude Code with Codex blockers before re-review.",
    )
    print(f"Task {task_id} marked NEEDS_FIX.")
    print("Next: address each Codex blocker, then re-run:")
    print("  python3 scripts/potucky_orchestrator.py prepare-prompts")
    print("  or:  python3 scripts/potucky_orchestrator.py auto-execute", task_id)


def cmd_print_next():
    data = load_tasks()
    tasks = data.get("tasks", [])

    for status in PRINT_NEXT_STATUSES:
        task = next((t for t in tasks if t.get("status") == status), None)
        if task:
            print(f"\nPOTUCKY ORCHESTRATOR — Next recommended action")
            print(f"  Active task: {task['id']} — {task['title']}  [{status}]")

            if status == "TODO":
                print("  Recommended: start this task")
                print(f"  Manual: python3 scripts/potucky_orchestrator.py run-next")
                print(f"  Auto:   python3 scripts/potucky_orchestrator.py auto-run-next")

            elif status == "IN_PROGRESS":
                print("  Recommended: finish executor work, then prepare Codex review")
                print(f"  Command: python3 scripts/potucky_orchestrator.py prepare-prompts")

            elif status == "NEEDS_REVIEW":
                print("  Recommended: run Codex audit")
                codex_file = PROMPTS_DIR / f"{task['id']}_codex_review_prompt.md"
                if codex_file.exists():
                    print(f"  Auto:         python3 scripts/potucky_orchestrator.py auto-review {task['id']}")
                    print(f"  Manual prompt: {codex_file}")
                else:
                    print(f"  Command: python3 scripts/potucky_orchestrator.py prepare-prompts")

            elif status == "NEEDS_FIX":
                print("  Recommended: return to executor with Codex blockers")
                executor_file = PROMPTS_DIR / f"{task['id']}_claude_executor_prompt.md"
                if executor_file.exists():
                    print(f"  Auto:         python3 scripts/potucky_orchestrator.py auto-execute {task['id']}")
                    print(f"  Manual prompt: {executor_file}")
                else:
                    print(f"  Command: python3 scripts/potucky_orchestrator.py prepare-prompts")

            elif status == "NEEDS_USER_APPROVAL":
                print("  Codex returned PASS. Review audit output and mark DONE manually.")
                stdout_log = LOGS_DIR / f"{task['id']}_codex_stdout.log"
                if stdout_log.exists():
                    print(f"  Codex output:  {stdout_log}")
                print(f"  Mark done:     python3 scripts/potucky_orchestrator.py mark-done {task['id']}")

            return

    blocked = [t for t in tasks if t.get("status") == "BLOCKED"]
    if blocked:
        print("\nPOTUCKY ORCHESTRATOR — Queue is blocked")
        for t in blocked:
            print(f"  BLOCKED: {t['id']} — {t['title']}")
        print("  Resolve blockers manually before the queue can advance.")
        return

    if tasks and all(t.get("status") == "DONE" for t in tasks):
        print("\nPOTUCKY ORCHESTRATOR — All tasks are DONE.")
        print("  Add the next task to scripts/potucky_agent_tasks.json to continue.")
        return

    print("\nNo tasks found. Add tasks to scripts/potucky_agent_tasks.json.")


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

COMMANDS = {
    "status": (cmd_status, 0),
    "doctor": (cmd_doctor, 0),
    "prepare-prompts": (cmd_prepare_prompts, 0),
    "run-next": (cmd_run_next, 0),
    "auto-run-next": (cmd_auto_run_next, 0),
    "auto-execute": (cmd_auto_execute, 1),
    "auto-review": (cmd_auto_review, 1),
    "mark-done": (cmd_mark_done, 1),
    "mark-blocked": (cmd_mark_blocked, 1),
    "mark-needs-fix": (cmd_mark_needs_fix, 1),
    "print-next": (cmd_print_next, 0),
}


def main():
    if len(sys.argv) < 2:
        print("POTUCKY ORCHESTRATOR")
        print("Usage: python3 scripts/potucky_orchestrator.py <command> [task-id]")
        print("Commands: " + ", ".join(COMMANDS))
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd not in COMMANDS:
        print(f"ERROR: Unknown command: {cmd}")
        print("Commands: " + ", ".join(COMMANDS))
        sys.exit(1)

    fn, arg_count = COMMANDS[cmd]
    if arg_count == 0:
        fn()
    elif arg_count == 1:
        if len(sys.argv) < 3:
            print(f"Usage: python3 scripts/potucky_orchestrator.py {cmd} <task-id>")
            sys.exit(1)
        fn(sys.argv[2])


if __name__ == "__main__":
    main()
