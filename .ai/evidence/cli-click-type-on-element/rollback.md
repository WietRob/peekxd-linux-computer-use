# Rollback

Branch: autonomy/peekxd/cli-click-type-on-element-20260621

To roll back after merge or local application, revert the task commit reported in the handoff:

```bash
git checkout main
git pull origin main
git revert <commit-hash-from-handoff>
pytest tests/ -q
```

Patch backup:
- `.ai/evidence/cli-click-type-on-element/changes.patch`

Manual rollback alternative:
1. Remove the `--on` option and optional semantic element path from `peekxd/cli.py` `click` command.
2. Remove the `--on` option and semantic focus/type path from `peekxd/cli.py` `type` command.
3. Remove the two added CLI tests from `tests/test_cli.py`.
4. Run `pytest tests/ -q`.
