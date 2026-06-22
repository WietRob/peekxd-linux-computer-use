# Rollback: peekxd yellow-build selftest argument parsing

Branch: autonomy/peekxd/yellow-20260622

## Rollback options

Preferred after commit exists:

```bash
git revert <yellow-build-commit-sha>
python3 -m pytest tests/ -q
```

If the branch has not been merged and can simply be discarded locally:

```bash
git checkout main
git branch -D autonomy/peekxd/yellow-20260622
```

If a remote branch is later pushed by the orchestrator and must be removed before merge:

```bash
git push origin --delete autonomy/peekxd/yellow-20260622
```

## Files changed by this build

- `selftest.sh`
- `tests/test_selftest.py`
- `changes.patch`
- `tests.md`
- `rollback.md`
- `evidence.md`

## Post-rollback verification

Run:

```bash
python3 -m pytest tests/ -q
```

Expected state after rollback: test suite returns to the pre-yellow behavior and the yellow-specific selftest argument parsing coverage is absent.

## No-revert policy note

Do not run `git revert` on product-code commits without the required human approval path if this repository's autonomy no-revert policy is in force. If approval is needed, prepare a revert-request.md instead of reverting directly.
