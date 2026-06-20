# Rollback: desktop-notification-provider

Branch: autonomy/peekxd/desktop-notification-provider-20260620

## Safe rollback options

1. Before merge: close the PR and delete the branch/worktree.
   ```bash
   git worktree remove /home/wietrob/projects/.worktrees/peekxd-desktop-notification-provider-20260620
   git branch -D autonomy/peekxd/desktop-notification-provider-20260620
   git push origin --delete autonomy/peekxd/desktop-notification-provider-20260620
   ```

2. After merge: revert the merge/squash commit with human approval per No-Revert policy.
   ```bash
   git revert <merged_commit_sha>
   python3 -m pytest tests/ -q
   ```

3. Manual patch rollback: remove `peekxd/notification.py` and `tests/test_notification.py`, then delete the `notify` command block from `peekxd/cli.py`.

## Verification after rollback

```bash
python3 -m pytest tests/ -q
```
