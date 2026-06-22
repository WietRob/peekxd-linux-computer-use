# Rollback

Task: orchestrator-screenshot-path-ghost-reference
Branch: autonomy/peekxd/orchestrator-screenshot-path-ghost-reference-20260622

## Preferred rollback after merge

Revert the single candidate commit on the integration branch:

```bash
git fetch origin
git checkout main
git pull origin main
git revert <commit-hash>
python -m pytest tests/ -q
```

Per buildroom policy, do not run `git revert` without human approval.

## Pre-merge rollback

If this branch has not been merged, close the PR and delete the branch:

```bash
git push origin --delete autonomy/peekxd/orchestrator-screenshot-path-ghost-reference-20260622
```

Local cleanup if needed:

```bash
git worktree remove /home/wietrob/.hermes/kanban/boards/curaops-vrp/workspaces/t_7d8bc640/peekxd
git -C /home/wietrob/projects/peekxd-linux-computer-use-ydotoold-socket-env-var-20260620 branch -D autonomy/peekxd/orchestrator-screenshot-path-ghost-reference-20260622
```

## Patch backup

The implementation patch is saved at:

```text
/home/wietrob/.hermes/kanban/boards/curaops-vrp/workspaces/t_7d8bc640/peekxd/.ai/evidence/t_7d8bc640/changes.patch
```
