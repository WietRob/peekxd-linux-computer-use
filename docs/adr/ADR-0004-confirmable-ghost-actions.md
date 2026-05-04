# ADR-0004: Confirmable Ghost Actions

**Status:** Accepted  
**Date:** 2026-04-25  
**Deciders:** Principal Engineer  
**Supersedes:** V3 overlay behavior (ADR-0003 implied)

## Context

The V3 Ghost Live Overlay (Softbox V3) introduced a user-facing confirmation surface for GHOST actions. Users can see a preview of what would happen and click Approve or Cancel. However, even with explicit user approval, GHOST actions are never executed — the overlay is purely informational.

## Problem

In the real orchestrator flow, safe actions (click, type "hello") are assigned to `Zone.SHADOW` by `ZoneDecision.decide()`, not `Zone.GHOST`. The GHOST zone is only reached when risk factors are present (destructive patterns, credentials, protected paths). The V3 overlay only operates in the GHOST zone branch, so safe actions in SHADOW zone execute directly with before/after snapshots — no overlay confirmation is available.

Users have no way to require explicit approval before a safe SHADOW action executes. Meanwhile, GHOST-zone actions (which have risk factors) should remain hard-blocked regardless of approval.

## Decision

Introduce a two-tier classification system and a SHADOW-to-confirmable-ghost routing path:

1. **HARD_BLOCKED_GHOST** — Always blocked, even with user approval. Never executes.
   Applies to actions in the GHOST zone (risk factors present) and force_ghost=True.
2. **APPROVABLE_GHOST** — May execute only when ALL of the following conditions are met:
   - `enable_ghost_overlay=True` (overlay must be active)
   - `enable_ghost_approval_execution=True` (new V4 flag, default off)
   - Action is in SHADOW zone with `risk_factors=[]` (safe action)
   - Action type is in the approvable set (click, type, type_text, hotkey, key)
   - Overlay user clicks Approve (not cancelled, not timed out)
   - `force_ghost=False` (forced ghost always hard-blocks)

### Routing Architecture

The real entry point for APPROVABLE_GHOST is NOT the GHOST zone branch. It is a new
routing path WITHIN the SHADOW zone branch:

```
ZoneDecision.decide("click", {x:100, y:200})
  → Zone.SHADOW, risk_factors=[]
  → _should_route_shadow_to_confirmable_ghost() returns True
    → overlay shown, classify_ghost_action() → APPROVABLE_GHOST
      → approved=True → _execute_action() called once
      → approved=False/timeout → blocked
```

The GHOST zone branch remains exclusively for hard-blocked cases (risk factors present,
force_ghost, unknown actions).

### Safety Rules (Hard-Blocked — Never Executable After Approval)

| Category | Pattern | Rationale |
|----------|---------|-----------|
| Credentials | text contains password, token, secret, api_key, private_key, ssh_key, credentials | Credential leakage risk |
| Destructive patterns | text contains rm, sudo, dd, mkfs, fdisk, shred, wipe, format, delete, remove, DROP, TRUNCATE | System destruction risk |
| Protected paths | output_path starts with /, /bin, /sbin, /etc, /boot, /dev, /proc, /sys, /lib, /usr/bin, /usr/sbin, /usr/lib, /usr/lib64 | System file risk |
| System key combos | hotkey contains ctrl+alt+delete, ctrl+alt+t | System-level key risk |
| Unknown actions | action not in known action set | Unpredictable behavior |
| Force ghost | force_ghost=True | CLI override — all actions must remain preview |

### Approvable Actions (Only When in SHADOW Zone With Zero Risk Factors)

| Action | Zone | Condition |
|--------|------|-----------|
| click | SHADOW | risk_factors=[] (safe click coordinates) |
| type | SHADOW | risk_factors=[] (safe text, no destructive/credential patterns) |
| type_text | SHADOW | risk_factors=[] (safe text) |
| hotkey | DIRECT* | risk_factors=[] (no system key combos) |
| key | DIRECT* | risk_factors=[] (no system key combos) |

*Note: hotkey/key are assigned to DIRECT zone, which is NOT SHADOW. The routing
helper checks `zone == SHADOW`, so hotkey/key currently do NOT enter the
confirmable-ghost path. Only SHADOW-zone actions (click, type, type_text) are
routable.

## Consequences

### Positive
- Users can require explicit approval before safe SHADOW actions execute
- Hard-blocked actions in GHOST zone remain impossible to execute, even with approval
- Default-off: existing V2 Shadow behavior unchanged until explicitly enabled
- Full audit trail: every action logs classification and execution decision
- V2 Shadow and V3 Preview-only behavior remain unchanged

### Negative
- Added complexity in zone routing (SHADOW branch now has two sub-paths)
- Potential for user confusion if they approve but action is still hard-blocked

### Neutral
- New CLI flag required: `--ghost-approval-execution`
- New orchestrator parameter: `enable_ghost_approval_execution`
- New helper method: `_should_route_shadow_to_confirmable_ghost()`
- Audit zone name for confirmable-ghost path: `shadow_confirmable_ghost`

## Acceptance Criteria

1. Normal click (SHADOW zone, no risk factors) + approved=True → executes exactly once
2. Normal type (SHADOW zone, no risk factors) + approved=True → executes exactly once
3. approved=False → never executes
4. Timed out → never executes
5. Cancelled → never executes
6. Destructive text "rm -rf /" (GHOST zone, risk factors) + approved=True → never executes
7. Credential text (GHOST zone, risk factors) + approved=True → never executes
8. Protected path (GHOST zone, risk factors) + approved=True → never executes
9. Unknown action (GHOST zone, risk factors) + approved=True → never executes
10. force_ghost=True + approved=True → never executes
11. Audit contains overlay_decision, approval_execution_decision, classification, executed flag
12. V2 Shadow behavior unchanged when V4 flags are off
13. V3 Preview-only behavior preserved when enable_ghost_approval_execution=False
14. Real ZoneDecision.decide() used (not mocked) for at least 10 tests proving the SHADOW routing path
