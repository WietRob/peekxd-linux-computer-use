# Evidence — t_f4abb84b semantic-source-fidelity-dynamic

## What changed

Implemented dynamic semantic source fidelity metadata in `peekxd/semantic.py` for the `build_semantic_snapshot()` envelope.

The snapshot `source` object now includes:

- `source_fidelity`: `high` when live accessibility produced elements with a real window, `medium` when elements exist but the window metadata used the synthetic fallback, and `low` when no elements were returned.
- `completeness_score`: `1.0` for complete live semantic data, `0.75` for semantic elements with fallback window metadata, and `0.0` for empty element results.
- `missing_apps`: the requested app name when an app-filtered request returns no elements.
- `fallback_used`: whether the snapshot relied on the synthetic fallback window.
- `warning`: `live_accessibility_returned_no_elements` when the accessibility provider returns an empty tree.

Added `tests/test_semantic_source_fidelity.py` to lock the empty-tree and populated-tree behavior.

## Why

The cycle-11 Dreamer input identified that hardcoded `source_fidelity: medium` masks AT-SPI/accessibility failures. With this change, downstream agents can distinguish a genuinely populated semantic UI from an empty accessibility response, while preserving the existing successful envelope shape and `safety_state` behavior.

## Scope control

- Product code files changed: 1 (`peekxd/semantic.py`).
- Test files changed: 1 (`tests/test_semantic_source_fidelity.py`).
- No main branch changes.
- No revert executed.
- No force push executed.
- No additional candidate implemented.

## Test evidence

See `tests.md` in this directory. Full suite result: `490 passed in 2.38s`.
