# Rollback: filesystem-path-provider

Branch: autonomy/peekxd/filesystem-path-provider-20260621

## Safe rollback options

1. Before merge: close the PR and delete the branch/worktree.
   ```bash
   git worktree remove /home/wietrob/projects/.worktrees/peekxd-filesystem-path-provider-20260621
   git branch -D autonomy/peekxd/filesystem-path-provider-20260621
   git push origin --delete autonomy/peekxd/filesystem-path-provider-20260621
   ```

2. After merge: revert the merge/squash commit with human approval per No-Revert policy.
   ```bash
   git revert <merged_commit_sha>
   python3 -m pytest tests/ -q
   ```

3. Manual patch rollback: remove `peekxd/filesystem.py` and `tests/test_filesystem.py`, then delete the `file` command group block from `peekxd/cli.py`.

## Verification after rollback

```bash
python3 -m pytest tests/ -q
```
