# Rollback: config-hermes-default

Branch: autonomy/peekxd/config-hermes-default-20260622
Commit: 25f6a4a

## Rollback options

Preferred after commit exists:

```bash
git revert <config-hermes-default-commit-sha>
python3 -m pytest tests/ -q
```

If this feature branch has not been merged and should be abandoned locally:

```bash
git checkout main
git branch -D autonomy/peekxd/config-hermes-default-20260622
```

If a remote branch is already pushed and must be removed:

```bash
git push origin --delete autonomy/peekxd/config-hermes-default-20260622
```

## Files to inspect after rollback

- `peekxd/config/manager.py`
- `README.md`
- `tests/test_config.py`

## Post-rollback verification

Run:

```bash
python3 -m pytest tests/ -q
```

Expected state: default vision provider in `DEFAULT_CONFIG` reverts to `openai`, and `test_config.py` no longer expects Hermes-first defaults.
