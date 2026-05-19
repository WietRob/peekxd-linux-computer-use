# ADR-0005: Peekaboo v3 Parity Roadmap

**Status:** Proposed
**Date:** 2026-05-19
**Author:** Hermes Analyst (Kanban task t_cdd3e2d2)
**Related:** docs/strategy/PEEKABOO_V3_PARITY_AUDIT.md

---

## Context

Peekaboo v3 (currently 3.2.1) is the original inspiration for peekxd and has matured into a comprehensive macOS desktop-automation platform. It introduces architectural primitives — **snapshot IDs**, **element IDs**, and **action-first accessibility interaction** — that significantly improve reliability and agent reasoning.

peekxd (currently v0.3.4) is a Linux-focused Python alternative. It already covers core vision + input primitives and has advanced safety features (Ghost, Shadow, Overlay, Zones) that Peekaboo lacks. However, peekxd's interaction model is stateless (coordinate-based or on-the-fly vision lookup), which limits agent reliability and reproducibility.

This ADR proposes adopting Peekaboo v3's *concepts* for peekxd v0.4.0 without turning peekxd into a macOS clone.

---

## Decision

We will adopt the following Peekaboo v3 concepts into peekxd v0.4.0:

1. **Snapshot IDs** as a first-class primitive.
2. **Element IDs** within snapshots for stable, referenceable UI elements.
3. **Unified CLI + MCP semantics** — both surfaces share the same snapshot/element model.
4. **Permissions doctor with real capture smoke tests**.
5. **Peekaboo-v3-inspired parity target** documented in strategy docs.

We will **not** copy Peekaboo's Swift implementation, macOS-specific APIs (TCC, ScreenCaptureKit, CoreGraphics), or macOS system integrations (Dock, Spaces, Menu Bar, Dialog).

---

## Why Peekaboo v3 as Reference Standard

- **Proven architecture:** Snapshot-based element addressing reduces agent hallucination and improves click accuracy.
- **MCP ecosystem alignment:** Peekaboo's MCP tool schema is well-integrated with Claude Code, Codex, and Cursor. Aligning peekxd's schema improves interoperability.
- **User expectation:** Users familiar with Peekaboo expect similar primitives (`see --json`, `click --on`, `type --on`).
- **Agent reliability:** Action-first accessibility (`set-value`, `perform-action`) is more reliable than synthetic input for form controls.

---

## Why peekxd Is Not a macOS Copy

| Dimension | Peekaboo v3 | peekxd v0.4.0 (planned) |
|---|---|---|
| Platform | macOS 15.0+ | Linux (X11, Wayland, WSLg) |
| Language | Swift 6.2 | Python 3.10+ |
| Capture | ScreenCaptureKit / CoreGraphics | `mss`, `PIL`, `grim`, WSLg fallback |
| Accessibility | macOS AX API | Linux AT-SPI2 |
| Distribution | Homebrew + npm + .app | pip + source |
| Safety | None | Ghost, Shadow, Overlay, Zones (Softbox family) |
| Vision | Tachikoma (multi-provider) | Hermes + OpenAI + Anthropic + Ollama |
| System integration | Dock, Spaces, Menu Bar, Dialog | App, Window, Menu (via AT-SPI2), Clipboard |

peekxd's value proposition is **Linux-native desktop automation with safety guardrails**, not a cross-platform Peekaboo port.

---

## Why see / snapshot / element-id Is the Next Architecture Lever

Currently, peekxd agents reason like this:

1. Capture screen.
2. Ask AI: "Where is the Submit button?"
3. AI returns approximate coordinates.
4. Click at coordinates.

This is **stateless, slow, and brittle**. Every click requires a full vision round-trip.

With snapshots:

1. `peekxd see --json` → captures screen, detects elements, returns `snapshot_id` + element list.
2. Agent reasons: "I need to click element `B1` in snapshot `SNAP-001`."
3. `peekxd click --on B1 --snapshot SNAP-001` → resolves coordinates from cached snapshot, clicks.

Benefits:
- **Speed:** No vision round-trip per action.
- **Reliability:** Coordinates validated against cached element positions.
- **Reproducibility:** Snapshots can be saved, audited, and replayed.
- **Agent clarity:** Element IDs are discrete symbols; easier for LLM reasoning than raw coordinates.

---

## Proposed CLI APIs (v0.4.0)

```bash
# Capture + analyze screen, return snapshot + elements
peekxd see --json
# Returns:
# {
#   "snapshot_id": "SNAP-20260519-001",
#   "elements": [
#     {"id": "B1", "name": "Submit", "role": "button", "position": {"x": 400, "y": 300}, "size": {"width": 80, "height": 30}},
#     {"id": "T1", "name": "Username", "role": "text_field", "position": {"x": 400, "y": 200}, "size": {"width": 200, "height": 30}}
#   ]
# }

# Click by element ID within a snapshot
peekxd click --on B1 --snapshot SNAP-20260519-001

# Type into an element by ID within a snapshot
peekxd type --on T1 --text "hello" --snapshot SNAP-20260519-001

# Inspect a snapshot (list all elements)
peekxd inspect --snapshot SNAP-20260519-001

# List active snapshots in session cache
peekxd snapshot list

# Clean old snapshots
peekxd snapshot clean --older-than 24
```

---

## Proposed MCP Tools (v0.4.0)

| Tool | Description |
|---|---|
| `peekxd_see` | Capture screen, detect elements, return `snapshot_id` + element list. |
| `peekxd_click_on` | Click element by ID within a snapshot. Args: `element_id`, `snapshot_id`, `button`. |
| `peekxd_type_on` | Type text into element by ID within a snapshot. Args: `element_id`, `snapshot_id`, `text`. |
| `peekxd_inspect_snapshot` | List all elements in a snapshot. Args: `snapshot_id`. |
| `peekxd_snapshot_list` | List active snapshots. |
| `peekxd_snapshot_clean` | Clean old snapshots. Args: `older_than_hours`, `snapshot_id`. |

These mirror Peekaboo's MCP tool semantics while using `peekxd_` prefix for namespace isolation.

---

## Consequences

### Positive
- Agent reliability improves significantly (fewer hallucinated coordinates).
- MCP interoperability with Peekaboo-aware clients.
- Reproducible sessions for debugging and auditing.
- Foundation for v0.4.x features: `set-value`, `perform-action`, workflow runner.

### Negative
- New dependency: snapshot cache management (disk usage, TTL, cleanup).
- Element detection must be deterministic enough for stable IDs across snapshots.
- AT-SPI2 integration for `set-value` / `perform-action` is DE-dependent and may have edge cases.
- Breaking change: existing coordinate-only scripts will still work, but agent behavior changes (prefers element IDs).

### Neutral
- No impact on existing safety features (Ghost, Shadow, Overlay, Zones).
- No impact on WSLg / Wayland / X11 capture backends.

---

## Alternatives Considered

1. **Keep stateless coordinate model**
   - Rejected: Agent reliability is too low; every action requires a vision round-trip.

2. **Copy Peekaboo's Swift implementation**
   - Rejected: Would require macOS; abandons Linux value proposition.

3. **Use accessibility tree as primary model (no vision)**
   - Rejected: AT-SPI2 alone misses visual context (images, canvas, non-AX apps). Vision + AX hybrid is optimal.

---

## References

- Peekaboo v3 source: https://github.com/openclaw/Peekaboo (cloned to `/home/roberto_schmidt/projects/Peekaboo-upstream`)
- peekxd source: `/home/roberto_schmidt/projects/peekxd-linux-computer-use`
- Gap-Matrix Audit: `docs/strategy/PEEKABOO_V3_PARITY_AUDIT.md`

---

*End of ADR-0005*
