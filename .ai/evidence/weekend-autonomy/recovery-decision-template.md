# Recovery Decision Template — Incident REVERT-20260619-1526

**Date:** 2026-06-19
**Status:** DECISION PENDING
**No execution without explicit Boss-Go**

---

## Option A — Accept Revert

**When:** If root cause shows VALID_REVERT (tests failed, scope violated)
**Consequence:**
- Branch stays with revert
- PR #1 closed or marked as blocked
- wayland-geometry candidate archived
- No further action needed

**Current status:** NOT RECOMMENDED — No evidence of valid revert reason

---

## Option B — Revert the Revert

**When:** If root cause shows INVALID_REVERT
**Requirements:**
- Normal commit (no force push)
- `git revert 61ced9a`
- Tests must pass
- PR updated

**Risk:** Medium — Branch history becomes confusing

**Current status:** NOT RECOMMENDED — Root cause is UNKNOWN, not proven INVALID

---

## Option C — New Clean Branch (RECOMMENDED)

**When:** If branch history is contaminated or unclear
**Steps:**
1. `git checkout main`
2. `git pull --ff-only`
3. `git checkout -b autonomy/peekxd/wayland-geometry-v2-YYYYMMDD`
4. Re-apply wayland-geometry changes cleanly
5. Tests
6. Commit
7. Push
8. New PR

**Advantages:**
- Clean history
- No revert confusion
- Clear audit trail

**Current status:** RECOMMENDED — Cleanest solution

---

## Option D — Evidence/Planning Only

**When:** If Weekend Autonomy should not resume
**Steps:**
- Document findings
- Close PR
- Archive branch
- No product-code changes

**Current status:** DEFAULT — Until revert-gate is proven

---

## Decision Matrix

| Option | Clean History | Tests Required | Risk | Effort | Recommendation |
|--------|-------------|----------------|------|--------|----------------|
| A | No | No | Low | Low | Not recommended |
| B | No | Yes | Medium | Low | Not recommended |
| C | Yes | Yes | Low | Medium | **Recommended** |
| D | Yes | No | None | Low | Default |

---

## Next Boss Decision

1. **Choose Option C (new clean branch)?**
2. **Choose Option D (evidence only, no autonomy)?**
3. **Require further investigation before any recovery?**

**No execution without explicit Boss-Go.**

---

*Recovery Decision Template for Incident REVERT-20260619-1526*
