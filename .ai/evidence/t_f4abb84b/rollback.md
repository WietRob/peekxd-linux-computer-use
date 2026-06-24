# Rollback — t_f4abb84b semantic-source-fidelity-dynamic

Branch: `autonomy/peekxd/semantic-source-fidelity-dynamic-20260622`

## Preferred rollback after merge

Revert the implementation commit after human approval, per project no-revert policy:

```bash
git checkout main
git pull origin main
git revert <commit-sha>
pytest tests/ -q
```

Do not run `git revert` from an agent without explicit human approval.

## Pre-merge rollback

If the PR is not merged yet, close the PR and delete the branch:

```bash
git push origin --delete autonomy/peekxd/semantic-source-fidelity-dynamic-20260622
git worktree remove /home/wietrob/.hermes/kanban/boards/curaops-vrp/workspaces/t_f4abb84b
```

## Patch backup rollback

A patch backup is stored at:

`/home/wietrob/.hermes/kanban/boards/curaops-vrp/workspaces/t_f4abb84b/.ai/evidence/t_f4abb84b/changes.patch`

To manually undo before commit, remove the added test/evidence files and restore `peekxd/semantic.py` from `origin/main`:

```bash
git restore --source=origin/main -- peekxd/semantic.py
git clean -fd -- tests/test_semantic_source_fidelity.py .ai/evidence/t_f4abb84b
pytest tests/ -q
```
