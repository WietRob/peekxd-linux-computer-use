# Rollback: peekxd green-build selftest fix

Branch: autonomy/peekxd/green-202606221326

## Pre-merge safety rollback

1) Do not merge yet: close this PR or keep the branch for review.
2) Delete the local branch:
   ```bash
   git checkout main
   git branch -D autonomy/peekxd/green-202606221326
   ```

3) Delete the remote branch:
   ```bash
   git push origin --delete autonomy/peekxd/green-202606221326
   ```

## Post-merge rollback (if merged)

1) Revert the merge commit with explicit approval (No-Revert policy requires review before any revert command):
   ```bash
   git revert <merge_or_squash_commit_sha>
   ```
2) Validate state:
   ```bash
   python3 -m pytest tests/ -q
   ```
   
## Verification

```bash
bash ./selftest.sh unit
bash ./selftest.sh desktop
python3 -m pytest tests/ -q
```