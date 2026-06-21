# Evidence

Candidate: semantic-element-state-change-detection
Task: t_79adce02
Branch: autonomy/peekxd/semantic-element-state-change-detection-20260621

## What changed

Implemented additive semantic state-change utilities in `peekxd/semantic.py`:

- `SemanticElement.state_diff(other)` reports added, removed, and changed state keys.
- `snapshot_diff(old, new)` compares two semantic snapshots or element lists by `element_id` and reports changed, added, removed, and unchanged elements.
- `wait_for_state_change(element_id, expected_state, timeout, poll_interval=0.5, ...)` polls semantic snapshots until an element reaches expected state values, then returns the matching `SemanticElement`.
- `_geometry_from_mapping()` now accepts existing `Geometry` instances so serialized-like in-memory element dictionaries can be rehydrated safely.

Added `tests/test_semantic_state_change.py` covering state diffs, snapshot diffs, envelope inputs, successful polling, and timeout behavior.

## Why

The Cycle 9 dreamer input identified a gap: PeekXD had semantic element `state` data but no utility for comparing two semantic snapshots or waiting for an element-level state transition. The implementation is bounded and additive to semantic utilities only.

## Constraints checked

- Exactly one candidate implemented: `semantic-element-state-change-detection`.
- Product files touched: `peekxd/semantic.py` and `tests/test_semantic_state_change.py`.
- No main branch edits; work was performed in isolated worktree `/home/wietrob/.hermes/kanban/boards/curaops-vrp/workspaces/t_79adce02/peekxd-linux-computer-use`.
- No force-push and no revert executed.

## Verification

See `tests.md` in this directory.
