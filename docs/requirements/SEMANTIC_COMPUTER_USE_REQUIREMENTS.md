# Semantic-First Computer-Use Requirements

## Status

Proposed for implementation in peekxd.

## Purpose

Define a computer-use model where control flow is built on semantic state (windows, UI trees, snapshots, and stable element references), and where visual capture is not the default or recurring representation. The model must support robust automation without requiring recurring screenshots and must prevent accidental visual capture.

This document applies to implementation and worker policy for no-MCP/no-screenshot modes.

## Hard Safety Gates

The following are forbidden in this model:

- periodic or recurring screenshot capture
- visual capture by default in terminal-orchestrated tasks
- MCP startup from generic operator loops when mode is "semantic-first"
- xdg-desktop-portal Screenshot calls by default
- PipeWire/ScreenCast session creation by default
- live computer-use from PM/spec-review lanes
- any background capture loop (polling/heartbeat screen dumps)

A visual-capture action is only permitted through an explicit manual gate that requires direct user approval in a bounded scope.

## 1. Core Design: Semantic-First State

All decision-making must be driven by semantic data:

- window metadata (application, title, focus, bounds)
- UI tree nodes (role, name, state, hierarchy)
- element references (stable IDs)
- explicit action plan + confirmation workflow

Raw raster images are treated as auxiliary evidence only, never as primary state.

## 2. Terminology

- `snapshot`: Captured semantic state of one UI turn.
- `snapshot_id`: Opaque identifier for a snapshot (e.g., `SNAP-20260529-001234-abc123`).
- `window_id`: Stable ID for a top-level window in the current snapshot.
- `element_id`: Stable identifier of a UI node within a snapshot.
- `semantic tree`: Structured hierarchy of windows/elements.
- `HUD`: Terminal/operator presentation layer for current state and queued actions.

## 3. Required Data Model

### 3.1 `snapshot` object

- `snapshot_id` (string): unique snapshot identifier
- `created_at` (ISO8601 timestamp, UTC)
- `ttl_seconds` (int): cache expiry
- `source` (enum): how this snapshot was produced
  - `live_accessibility`
  - `cached_tree`
  - `user_provided`
- `source_fidelity` (enum): `high|medium|low`
- `windows` (array)
  - `window_id`
  - `app_id`
  - `title`
  - `is_focused`
  - `geometry`
- `elements` (array)
  - `element_id`
  - `window_id`
  - `role`
  - `name` / `label`
  - `value` / `placeholder`
  - `state` (enabled/disabled, checked, selected, expanded)
  - `path` (hierarchy path for debugging)
  - `bbox`
  - `metadata`

### 3.2 `snapshot_id` model

- Must be globally unique across process lifetime.
- Should not leak sensitive workspace path names.
- Must be accepted as a mandatory parameter on all element-targeted actions.
- Optional fallback: when an action is issued without `snapshot_id`, workers may attempt fallback resolution to the latest snapshot from the same focused window within TTL only if explicitly approved by operator policy.

### 3.3 `element_id` model

- Must be stable within a snapshot and derived from deterministic structure index.
- Must include role group prefix in human-readable form where practical (for example `W1-B3`, `W1-T1`).
- Must be resolvable only against the snapshot it was created from.
- If an `element_id` is invalid for the given `snapshot_id`, action must fail fast and return corrective action suggestions (`refresh_semantic_tree`, `inspect_window`, `request_capture_gate`).

## 4. UI-Tree / Window Metadata Source Hierarchy

Resolution priority (highest first):

1. **Live accessibility source**
   - Preferred source where available.
   - Must provide window graph + role tree + element IDs.
   - No screenshot dependency.

2. **In-memory semantic cache**
   - Reuse the latest compatible snapshot within TTL.
   - Must still include `source="cached_tree"` and `source_fidelity="low"`.

3. **Declared user input context**
   - Use explicit user-provided target descriptions only when neither source 1 nor 2 is available.
   - Must include `source="user_provided"` and an explicit confidence warning in HUD.

4. **No semantic source fallback**
   - If no source is available, return a schema-complete blocking error.
   - Block reason must explain why no UI tree can be produced.
   - Include explicit manual visual-capture path only with user approval (see section 7).

## 5. Terminal HUD Presentation

PM/worker terminal output should not rely on image previews. HUD should present semantic state only:

- Snapshot banner: `snapshot_id`, source, age, ttl_remaining
- Focused window line: `window_id`, app title, focus state
- Active element shortlist: top 6 actionable elements (`element_id`, `role`, `name`, confidence, state)
- Planned action queue with statuses (`PLAN`, `PREVIEW`, `BLOCKED`, `EXECUTED`)
- No more than 20 terminal lines per turn for normal operations (compact summary first)

Optional detailed mode:
- emit JSON block for operators and downstream automation
- include diff-like element updates between current and prior snapshot when available

## 6. Plan-Preview-Execute UX

Any mutation-capable action must follow this sequence by default:

1. **Plan**
   - Worker computes one or more candidate actions using `snapshot_id` + `element_id`.
   - Plans must include `plan_id`, `snapshot_id`, target `window_id`, `element_id`, and predicted risk impact.

2. **Preview**
   - Show a deterministic, no-side-effect summary of the planned change:
     - what will execute
     - why selected
     - fallback alternatives
     - required confirmation scope
   - No screen capture during preview.

3. **Execute**
   - Runs only after explicit pass-through from operator or workflow gate.
   - Logs execution result (`ok|blocked|error`) and resulting snapshot delta (if available).

Replay behavior:
- Re-run action only after plan IDs do not match previous executed plan.
- Duplicate actions without new plan approval must be idempotently suppressed.

## 7. Manual Visual-Capture Gate

Visual capture is an explicit exception flow.

- Default state: capture disabled.
- Allowed only via direct user command in one of:
  - separate no-MCP/no-capture worker profile prepared for that purpose
  - explicit user request containing all of:
    - reason
    - scope
    - timeout
    - consent token/approval line
- One-shot capture only; no recurring capture.
- Capture must include explicit log entry:
  - `visual_capture_enabled=true`
  - `approved_by=user`
  - `duration_seconds`
  - `capture_reason`
  - `captured_by` profile
- After capture, return to semantic-first mode automatically.

## 8. No-Background-Capture Invariant

The system **must** enforce all of:

- No background tasks that call capture/screenshot APIs.
- No background queue with screen polling.
- No PipeWire / screencast session retained for non-approved lanes.
- No periodic refresh of visual state.
- If capture attempt fails due to denied approvals or missing profile, fail closed and keep semantic lane active.

## 9. Worker Policy

### 9.1 PM lane (this lane)

- This lane is for requirements/spec/code-review only.
- It MUST NOT run any live capture or mouse/keyboard actions.
- It MUST NOT spawn peekxd MCP server.
- It MUST produce human-readable artifact + acceptance criteria.

### 9.2 Execution lanes

- Actual action execution in live modes runs in dedicated profiles that explicitly allow no-capture exceptions.
- Live lanes must:
  - use semantic-first defaults,
  - request capture only through section 7 gate,
  - include audit logging and no-background-capture enforcement.

### 9.3 Failure handling

- If requested to perform live computer-use without valid gate/approval, worker must refuse with blocking reason.
- If semantic source is missing or stale, worker should propose:
  - `refresh_semantic_tree` (semantic), then
  - optional `manual_capture_request`.

## 10. Acceptance Criteria

1. All worker planning and action selection in this mode uses semantic snapshot + element metadata as the primary state.
2. No recurring capture loop exists in this mode.
3. `snapshot_id` is required for element-directed operations.
4. Actions with invalid `snapshot_id`/`element_id` return structured correction guidance.
5. Terminal HUD never prints binary image data by default.
6. Visual capture can only be triggered via explicit manual gate (approval + bounded scope + timeout).
7. If no snapshot source is available, the system blocks deterministically and suggests next semantic action + optional gated capture path.
8. PM/spec lane can generate requirements and reviews without any capture command executed.
9. All executed actions include plan id, snapshot id, and element provenance in logs.
10. Replaying the same stale plan does not execute again without re-approval.

## 11. Non-Goals

- Implementing image-recognition as primary automation driver.
- Replacing all visual capture in all environments.
- Live screenshot-based control loops.
- Cross-profile policy orchestration without explicit user request.
- Auto-enabling visual tools in default semantic-first workflows.

## 12. Open Items

- Decide policy for stale cached trees under rapid UI churn.
- Finalize `element_id` entropy/encoding if high collision rates are observed.
- Define exact JSON schema versions for HUD preview payloads.
- Define retention policy for semantic snapshots under multi-session mode.
