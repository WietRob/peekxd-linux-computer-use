# Rollback — ydotoold-socket-env-var

Date: 2026-06-20T21:48:40+02:00
Branch: autonomy/peekxd/ydotoold-socket-env-var-20260620

## Safe rollback after merge

1. Find the merge/squash commit that introduced `ydotoold-socket-env-var`.
2. Revert it with human approval, per project policy:
   `git revert <commit-sha>`
3. Run verification:
   `pytest tests/test_input.py -q`
   `pytest tests/ -q`

## Patch-level rollback before merge

From this worktree, remove the feature branch changes with:

`git restore --source=origin/main -- peekxd/input/wayland.py tests/test_input.py .ai/evidence/weekend-autonomy/ydotoold-socket-env-var/rollback.md`

Then verify:

`pytest tests/test_input.py -q`

## What rollback removes

- `PEEKXD_YDOTOOLD_SOCKET` override lookup.
- `XDG_RUNTIME_DIR/ydotoold/socket` fallback lookup.
- The related Wayland input availability tests.
