# Rollback — wayland-geometry-v2

**Date:** 2026-06-19
**Branch:** `autonomy/peekxd/wayland-geometry-v2-20260619`
**Status:** COMPLETED
**Scope:** `peekxd/window/wayland.py`
**Product Code Commit:** `ccf5f83`
**Evidence Commit:** `b3c3d40`

---

## Changed Files

| File | Lines | Description |
|------|-------|-------------|
| `peekxd/window/wayland.py` | +51, -7 | Add swaymsg geometry fallback for wlrctl window listing |

---

## Rollback Command

```bash
git revert ccf5f83
```

No force-push needed. Revert creates a new commit that undoes the product code change.

For evidence cleanup (optional):
```bash
git revert b3c3d40
```

---

## Tests

| Test Suite | Result |
|------------|--------|
| `tests/test_window.py -k wayland` | 18/18 PASSED |
| `tests/test_cli.py` | 24/24 PASSED |

---

## Risks

| Risk | Mitigation |
|------|------------|
| swaymsg not available | Graceful fallback to placeholder geometry |
| swaymsg JSON parse error | Exception caught, fallback to placeholder |
| Window name mismatch | Both name and app_id mapped to geometry |

---

## Notes

- This is a clean recovery from Incident REVERT-20260619-1526
- Old branch `autonomy/peekxd/wayland-geometry-20260619-1105` is superseded
- Old PR #1 is superseded
- No force-push used
- No revert-the-revert on contaminated branch

---

*Rollback for wayland-geometry-v2 recovery*
