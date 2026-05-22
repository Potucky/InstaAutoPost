# POTUCKY ORCHESTRATOR — Claude Code Executor Prompt
# Generated: 2026-05-22 00:00 UTC
# Orchestrator: POTUCKY ORCHESTRATOR v0.1.0

## PROJECT
Path: /Users/vasylpopovich/Projects/InstaAutoPost

## TASK
ID:     IAP-001
Title:  Read-only safety baseline
Status: DONE
Branch: agent/iap-001-orchestrator-bootstrap

## STRICT SCOPE
You are operating under POTUCKY ORCHESTRATOR safety rules.
Work ONLY within the declared allowed files below.
Do NOT modify any file outside this list.

## ALLOWED FILES
  - CLAUDE.md
  - docs/AGENT_REVIEW_RULES.md
  - docs/AGENT_RUN_REPORT.md
  - docs/AGENT_TASK_QUEUE.md
  - docs/POTUCKY_ORCHESTRATOR.md
  - docs/PROJECT_STATUS.md
  - docs/SECURITY_RULES.md
  - scripts/potucky_agent_prompts/
  - scripts/potucky_agent_tasks.json
  - scripts/potucky_orchestrator.py

## FORBIDDEN ACTIONS
The following actions are STRICTLY PROHIBITED for this task:
  - publish
  - deploy
  - supabase_write
  - migration_apply
  - secret_print
  - env_print
  - github_actions_run
  - commit
  - push
  - merge

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
  - pwd
  - git status --short
  - git branch --show-current
  - git ls-files .github/workflows || true
  - find docs -maxdepth 2 -type f | sort || true

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
Bootstrap task for POTUCKY ORCHESTRATOR safety baseline. Scope was expanded because the real bootstrap created docs and orchestrator scripts.

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
