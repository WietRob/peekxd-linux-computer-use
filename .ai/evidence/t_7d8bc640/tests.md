# Test Plan and Results

Task: orchestrator-screenshot-path-ghost-reference

## RED

Command:

```bash
python -m pytest tests/test_orchestrator_overlay.py::TestGhostWithOverlay::test_force_ghost_overlay_ignores_stale_screenshot_path -q
```

Result before product-code change:

```text
FAILED tests/test_orchestrator_overlay.py::TestGhostWithOverlay::test_force_ghost_overlay_ignores_stale_screenshot_path
AssertionError: assert '/tmp/stale-screen.png' is None
```

This proved the orchestrator was still forwarding a stale `screen_state["path"]` into `OverlayRequest.screenshot_path` even though the semantic-only `_see()` path does not provide screenshots.

## GREEN / Regression

Command:

```bash
python -m pytest tests/test_orchestrator_overlay.py::TestGhostWithOverlay::test_force_ghost_overlay_ignores_stale_screenshot_path tests/test_real_confirmable_ghost.py::TestRealConfirmableGhostTimedOut::test_click_overlay_ignores_stale_screenshot_path -q
```

Result:

```text
2 passed in 0.08s
```

## Focused orchestrator suite

Command:

```bash
python -m pytest tests/test_orchestrator_overlay.py tests/test_real_confirmable_ghost.py tests/test_orchestrator_confirmable_ghost.py -q
```

Result:

```text
38 passed in 0.12s
```

## Full suite

Command:

```bash
python -m pytest tests/ -q
```

Result:

```text
488 passed in 2.47s
```
