# Rollback Plan

Candidate: semantic-element-state-change-detection
Branch: autonomy/peekxd/semantic-element-state-change-detection-20260621

## Preferred rollback after merge

Revert the candidate commit on a new branch after human approval:

```bash
git checkout main
git pull origin main
git checkout -b rollback/semantic-element-state-change-detection-20260621
git revert <commit-hash>
python3 -m pytest tests/ -q
git push -u origin HEAD
```

Do not run `git revert` without human approval under the buildroom no-revert policy.

## Manual rollback before merge

If this branch has not been merged, close the PR and delete the branch:

```bash
git push origin --delete autonomy/peekxd/semantic-element-state-change-detection-20260621
git worktree remove /home/wietrob/.hermes/kanban/boards/curaops-vrp/workspaces/t_79adce02/peekxd-linux-computer-use
```

## Patch-level rollback

Remove these additions:

- `SemanticElement.state_diff()` from `peekxd/semantic.py`
- `_coerce_semantic_elements()` from `peekxd/semantic.py`
- `snapshot_diff()` from `peekxd/semantic.py`
- `wait_for_state_change()` from `peekxd/semantic.py`
- the `Geometry` passthrough branch in `_geometry_from_mapping()` if no longer needed
- `tests/test_semantic_state_change.py`

Then verify:

```bash
python3 -m pytest tests/ -q
```
