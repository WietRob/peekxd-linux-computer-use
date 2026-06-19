# Evidence — GREEN Candidate: task-quality

**Date:** 2026-06-19
**Branch:** `autonomy/peekxd/task-quality-20260619-1015`
**Status:** IN PROGRESS
**Scope:** `.ai/`, `docs/`, `scripts/`

---

## Problem

Generic cycle tasks do not reflect actual work done. Task titles like "Researcher — peekxd Cycle 1" provide no information about what was actually researched.

## Evidence

- 73 PeekXD Tasks total
- 45 generic cycle tasks (61.6%)
- Only 28 meaningful tasks (38.4%)
- Worktree evidence exists but is not reflected in task titles

## Solution

Implement Quality Gate in Scheduler:
1. Extract concrete problem from repo before task creation
2. Check for duplicate tasks
3. Create specific title with problem description
4. Write evidence-only brief when no concrete problem found

## Changes

- `bounded_scheduler_v051.py`: Added `_extract_concrete_problem`, `_check_duplicate`, `_write_evidence_only_brief`
- Task titles now: `Researcher — peekxd: identify screenshot fallback gaps` instead of `Researcher — peekxd Cycle 1`

## Verification

- `hermes kanban list | grep -c 'Cycle'` should decrease over time
- New tasks should have specific titles
- Evidence-only briefs should be written for skipped tasks

## Rollback

- `git revert` on scheduler changes
- Or: restore previous scheduler version from backup

---

*Evidence for GREEN Candidate: task-quality*
