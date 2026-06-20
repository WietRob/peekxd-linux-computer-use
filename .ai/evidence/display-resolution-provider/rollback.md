# Rollback

Candidate: display-resolution-provider
Branch: autonomy/peekxd/display-resolution-provider-20260620

## If merged and rollback is approved

1. Revert the commit that introduced this candidate:
   `git revert <commit-sha>`
2. Run the regression suite:
   `pytest tests/ -q`
3. Push the rollback commit and open a review PR.

## Manual patch rollback

Remove the additive display provider and CLI entry points:

- Delete `peekxd/display.py`
- Delete `tests/test_display.py`
- Remove the `display` Click group and `display list` command from `peekxd/cli.py`
- Remove this evidence directory if it is no longer needed: `.ai/evidence/display-resolution-provider/`

No system state or configuration is mutated by this feature; the provider is query-only.
