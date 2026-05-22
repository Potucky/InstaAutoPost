# AGENT_REVIEW_RULES.md

Rules for Codex operating as the read-only reviewer for InstaAutoPost agent tasks.

---

## Role

Codex is a **read-only reviewer**. Codex reads the completed work and returns a structured review verdict.

Codex **may** run safe read-only inspection commands to gather evidence — for example:
`git status --short`, `git diff HEAD`, `git branch --show-current`, `cat`, `head`, `grep`,
`find` (on project files only). These are permitted when needed to verify scope, changed
files, and report completeness.

Codex **must not** write files, modify code, commit, push, deploy, publish, apply migrations,
run destructive SQL, print secrets or env var values, or perform any action that modifies state
outside the current inspection. Even when running inspection commands, Codex must not read
`.env` files or any file known to contain secrets.

---

## What Codex Must Check

For every task under review, Codex must evaluate all of the following areas:

1. **Scope compliance** — Did the agent work only within the task's declared `Scope` and `Allowed files`? Flag any file touched that is not on the allowed list.

2. **Changed files** — Are the changed files appropriate for this task? Are any surprising files modified?

3. **Forbidden actions** — Did the agent violate any item in the task's `Forbidden actions` list? Treat any violation as a FAIL blocker.

4. **Runtime risks** — Are there commands or code paths that could have unintended runtime effects (process spawns, network calls, filesystem writes outside scope)?

5. **Security risks** — Any hardcoded credentials, tokens, or secrets in code or logs? Any insecure patterns (command injection, SQL injection, XSS, open redirects, exposed credentials)?

6. **Supabase / schema risks** — Any raw SQL, schema changes, or Supabase writes outside of the declared scope? Any drift introduced between repo migrations and live schema?

7. **GitHub Actions risks** — Any workflow changes that enable scheduled publishing, remove safety guards, add new secrets references, or change trigger conditions?

8. **Publishing / API side effects** — Any code path that could trigger a real Instagram or TikTok publish, even indirectly?

9. **Secrets leakage** — Any output, log line, or file that contains or could expose `IG_ACCESS_TOKEN`, `SUPABASE_SERVICE_ROLE_KEY`, refresh tokens, client secrets, or signed URL query parameters?

10. **Documentation consistency** — Are docs updated when required by `docs/ROADMAP.md` or `CLAUDE.md` documentation rules? Do new facts contradict existing docs?

---

## Review Output Format

Codex must return a structured review in this exact format:

```
Codex Review — Task ID: <IAP-XXX>
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
  <One paragraph. If PASS: confirm the task is safe to mark DONE. If FAIL: describe
   what must be fixed before re-review and do not allow the task to advance.>
```

---

## Pass / Fail Rules

- **PASS** requires zero blockers across all ten check areas.
- **FAIL** if any blocker exists in any check area.
- Suggestions are non-blocking; they do not prevent PASS.
- If Codex cannot access the required files or run report, return FAIL with blocker: `run report or changed files not available for review`.

---

## After Review

- If **PASS**: task owner moves task to `DONE` in `docs/AGENT_TASK_QUEUE.md` and records the Codex result in `docs/AGENT_RUN_REPORT.md`.
- If **FAIL**: task owner moves task to `NEEDS_FIX`, addresses each blocker, and re-submits for Codex review. The queue does not advance until PASS.
