# Rollback Plan

Candidate: semantic-element-action-mapping
Branch: autonomy/peekxd/semantic-element-action-mapping-20260621

## Preferred rollback after merge

Use a normal git revert of this candidate commit only, after human approval per the No-Revert Policy:

```bash
git checkout main
git pull origin main
git revert <candidate-commit-sha>
pytest tests/ -q
```

Do not force-push and do not merge rollback changes without review.

## Pre-merge rollback

If this branch is still under review, close the PR and delete the branch:

```bash
git push origin --delete autonomy/peekxd/semantic-element-action-mapping-20260621
```

Then remove the local worktree/branch if desired:

```bash
git worktree remove /home/wietrob/.hermes/kanban/boards/curaops-vrp/workspaces/t_2e6d2054
git -C /home/wietrob/projects/peekxd-linux-computer-use-ydotoold-socket-env-var-20260620 branch -D autonomy/peekxd/semantic-element-action-mapping-20260621
```

## Patch backup

Patch backup for this candidate is at:

`/home/wietrob/.hermes/kanban/boards/curaops-vrp/workspaces/t_2e6d2054/.ai/evidence/t_2e6d2054/changes.patch`

To reverse locally before commit/merge, apply it in reverse from the repository root:

```bash
git apply -R .ai/evidence/t_2e6d2054/changes.patch
pytest tests/ -q
```
