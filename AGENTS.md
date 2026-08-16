# Hermes Company Project Rules

## Project

NOAVIA AI Support Ticket System

Canonical working directory:

C:/Users/saiyu/Desktop/projects/Noavia/AI_Support_Ticket_System

## Execution

- Kanban is the authoritative active-task state.
- Follow the assigned card and its acceptance criteria.
- Inspect existing implementation before proposing replacement work.
- Do not modify unrelated files.
- Run relevant tests after changes.
- Preserve reproducibility.
- Existing repository state is the source of truth.

## Review

- The implementer must not be the final reviewer of its own work.
- Substantial changes require an appropriate independent reviewer.
- Reviewer findings must include evidence.
- CHANGES REQUIRED routes back to implementation.
- PASS requires acceptance criteria and evidence.

## Safety

- Never place secrets, API keys, passwords, tokens, or private keys in source files, documentation, Kanban comments, or Hindsight.
- Do not perform destructive or irreversible operations without the approval required by company governance.
- Do not make production changes, purchases, legal commitments, external-account changes, or security-risk acceptance without required Owner approval.
- Do not silently broaden permissions.

## Git

- Do not force-push.
- Do not rewrite shared history.
- Do not push to a remote unless the task explicitly authorizes it.
- Keep changes scoped to the assigned task.

## Memory

- Project-specific lessons remain project-scoped unless deliberately promoted.
- Hindsight is institutional memory, not the active task tracker.
- Canonical project files and company governance override remembered information when they conflict.

## Current Concurrency Rule

Until remote per-task Git worktree isolation is implemented, multiple agents may inspect this repository concurrently, but only one write-producing implementation flow may modify this working tree at a time.
