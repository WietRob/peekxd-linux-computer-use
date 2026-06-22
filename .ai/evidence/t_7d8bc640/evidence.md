# Evidence

Task: t_7d8bc640
Candidate: orchestrator-screenshot-path-ghost-reference
Branch: autonomy/peekxd/orchestrator-screenshot-path-ghost-reference-20260622

## What changed

- Removed the local `screenshot_path = screen_state.get("path")` ghost reference from the GHOST overlay path in `peekxd/agent/orchestrator.py`.
- Removed the same ghost reference from the SHADOW-to-confirmable-ghost overlay path.
- Let `ZoneDecision.create_ghost_preview()` and `OverlayRequest` use their default `screenshot_path=None` behavior.
- Added regression tests proving both ghost overlay paths ignore stale screenshot paths when screenshot access is absent.

## Why

`AgentOrchestrator._see()` is semantic-only and always returns `{"path": None, ...}`. Passing `screen_state.get("path")` into preview/overlay construction is now a stale screenshot-era ghost reference. Removing it keeps the overlay flow consistent with the semantic-only design and prevents future callers from accidentally reviving screenshot-dependent behavior through a stale `screen_state` dict.

## Files changed

Product code:

- `peekxd/agent/orchestrator.py`

Tests:

- `tests/test_orchestrator_overlay.py`
- `tests/test_real_confirmable_ghost.py`

Evidence artifacts:

- `.ai/evidence/t_7d8bc640/changes.patch`
- `.ai/evidence/t_7d8bc640/tests.md`
- `.ai/evidence/t_7d8bc640/rollback.md`
- `.ai/evidence/t_7d8bc640/evidence.md`

## Verification

- RED test observed before product-code change: `test_force_ghost_overlay_ignores_stale_screenshot_path` failed because `OverlayRequest.screenshot_path` was `'/tmp/stale-screen.png'`.
- Focused regression tests passed: `2 passed in 0.08s`.
- Focused orchestrator suite passed: `38 passed in 0.12s`.
- Full suite passed: `488 passed in 2.47s`.
