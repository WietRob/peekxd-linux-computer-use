# Rollback: selftest green diagnostics

Branch: autonomy/peekxd/green-202606221326

## Safe rollback options

1. Before merge: close the PR and delete branch `autonomy/peekxd/green-202606221326`.
2. Undo the changes directly:
   ```bash
   git checkout main
   git checkout -- selftest.sh tests/test_selftest.py rollback.md
   ```

3. Delete the branch locally and remotely if desired:
   ```bash
   git branch -D autonomy/peekxd/green-202606221326
   git push origin --delete autonomy/peekxd/green-202606221326
   ```

## Verification after rollback

```bash
python3 -m pytest tests/ -q
bash ./selftest.sh unit
```