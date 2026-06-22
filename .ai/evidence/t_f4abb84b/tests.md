# Tests — t_f4abb84b semantic-source-fidelity-dynamic

## Test plan

1. Add focused tests for dynamic semantic source fidelity metadata:
   - Empty accessibility tree reports low fidelity, zero completeness, requested app in missing_apps, fallback_used=true, and warning.
   - Populated accessibility tree with a real window reports high fidelity, full completeness, no missing apps, fallback_used=false, and no warning.
2. Run the focused new test file to verify RED before implementation.
3. Run focused semantic-related tests after implementation.
4. Run the full pytest suite before commit.

## Results

- RED check: `pytest tests/test_semantic_source_fidelity.py -q`
  - Result before implementation: 2 failed as expected because `source_fidelity` was hardcoded to `medium`.
- GREEN focused check: `pytest tests/test_semantic_source_fidelity.py -q`
  - Result: 2 passed in 0.02s.
- Related semantic regression check: `pytest tests/test_semantic_source_fidelity.py tests/test_semantic_action_mapping.py tests/test_semantic_state_change.py -q`
  - Result: 12 passed in 0.04s.
- Full suite: `pytest tests/ -q`
  - Result: 490 passed in 2.38s.
- Lint attempt: `python3 -m ruff check peekxd/semantic.py tests/test_semantic_source_fidelity.py`
  - Result: not run because `ruff` is not installed in the active environment (`No module named ruff`).
