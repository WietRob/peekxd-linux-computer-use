# Rollback/Revert Policy — Hermes Weekend Autonomy

**Date:** 2026-06-19
**Status:** ACTIVE
**Scope:** All autonomous product-code changes

---

## Rule

**NO autonomous agent may revert product-code commits without ALL of the following:**

1. **Source Commit**
   - Full commit hash
   - Branch name
   - Author

2. **Reason**
   - Clear explanation why revert is necessary
   - Not just "This reverts commit X"

3. **Failing Test**
   - Which test failed
   - Test output
   - How to reproduce

4. **Scope Violation**
   - What scope was violated
   - Which file(s) were outside allowed paths

5. **Reviewer Evidence**
   - Reviewer recommendation
   - Reviewer profile used
   - Review timestamp

6. **Rollback Plan**
   - How to restore if revert is wrong
   - `git revert <revert-commit>` command
   - Tests to verify restoration

7. **Explicit Approval**
   - Human approval OR
   - Documented approval state in evidence
   - Approval timestamp

## Prohibited Actions

| Action | Status |
|--------|--------|
| Auto-revert without evidence | ❌ FORBIDDEN |
| Revert without failing test | ❌ FORBIDDEN |
| Revert without scope violation | ❌ FORBIDDEN |
| Revert without reviewer evidence | ❌ FORBIDDEN |
| Revert without rollback plan | ❌ FORBIDDEN |
| Revert without explicit approval | ❌ FORBIDDEN |

## Allowed Actions

| Action | Status |
|--------|--------|
| Document failing test | ✅ ALLOWED |
| Document scope violation | ✅ ALLOWED |
| Request reviewer | ✅ ALLOWED |
| Write evidence | ✅ ALLOWED |
| Recommend revert (not execute) | ✅ ALLOWED |
| Stop and wait for human | ✅ ALLOWED |

## Enforcement

### Scheduler
- Add `revert_policy` check before any revert
- If any of 7 criteria missing: STOP and document

### Builder Profile
- "If tests fail: STOP, document, do NOT revert"
- "If scope violated: STOP, document, do NOT revert"

### Reviewer Profile
- "Recommend revert, do NOT execute revert"
- "Write evidence, wait for human approval"

### Evidence Template

```markdown
# Revert Request

**Source Commit:** 
**Reason:** 
**Failing Test:** 
**Scope Violation:** 
**Reviewer Evidence:** 
**Rollback Plan:** 
**Approval:** 
```

## Incident History

| Date | Incident | Status |
|------|----------|--------|
| 2026-06-19 | REVERT-20260619-1526 | UNDER INVESTIGATION |

---

*Rollback/Revert Policy for Hermes Weekend Autonomy*
