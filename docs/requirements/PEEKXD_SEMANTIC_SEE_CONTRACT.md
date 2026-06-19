# peekxd semantic contract: `see --semantic` CLI/MCP/API

This contract is for task t_2fdf5767.
It is docs/design-only: no live capture/tool execution.

## 1) Purpose

`peekxd see --semantic` becomes the canonical state primitive for both terminal and MCP workflows.
It returns a semantic snapshot (element tree with IDs + bounding boxes + optional window context) and can optionally attach one visual evidence image via `--visual --once`.

## 2) ID model

- `snapshot_id` (required for all element operations)
  - format: `snap_<YYYYMMDD>_<rand10>`
  - example: `snap_20260529_9wz2qv1h6k`
- `window_id` (snapshot-local/semantically meaningful)
  - example: `W1`, `W2`
- `element_id` (operator-facing short id)
  - example: `W1-B3`, `W1-T4`
- `raw_element_id` (provider-native) retained in snapshot for replay
  - example from AT-SPI2: `0:3:14`

## 3) Canonical JSON contract

Top-level envelope for `peekxd see --semantic --json` and MCP `peekxd_see_semantic`:

```json
{
  "schema_version": "peekxd.see.v1",
  "command": "see --semantic",
  "request": {
    "app": "firefox",
    "cache_policy": "prefer_live",
    "ttl_seconds": 30,
    "max_elements": 60,
    "visual": false,
    "visual_once": false
  },
  "snapshot": {
    "snapshot_id": "snap_20260529_9wz2qv1h6k",
    "created_at": "2026-05-29T23:14:12.314Z",
    "ttl_seconds": 30,
    "cache_ttl_remaining_seconds": 29.9,
    "cached": false,
    "source": {
      "kind": "live_accessibility",
      "provider": "atspi2",
      "source_fidelity": "medium"
    },
    "windows": [
      {
        "window_id": "W1",
        "app_id": "firefox",
        "title": "Peekxd docs",
        "is_focused": true,
        "geometry": { "x": 0, "y": 0, "width": 1366, "height": 768 }
      }
    ],
    "elements": [
      {
        "element_id": "W1-B3",
        "raw_element_id": "0:4",
        "window_id": "W1",
        "role": "button",
        "name": "Search",
        "label": "Search",
        "bbox": { "x": 1240, "y": 18, "width": 38, "height": 24 },
        "state": { "enabled": true, "focused": false },
        "actions": ["click", "focus"],
        "path": "W1 > toolbar > address_bar > button[3]",
        "confidence": 0.96
      }
    ]
  },
  "safety_state": {
    "state": "OK",
    "code": "SEMANTIC_OK",
    "reason": "live_accessibility_success"
  },
  "meta": {
    "cache_id": "cache_0003ab",
    "cache_hit": false,
    "request_id": "req_58f4",
    "elapsed_ms": 42
  },
  "result": { "ok": true, "error": null }
}
```

Error envelope:

```json
{
  "schema_version": "peekxd.see.v1",
  "command": "see --semantic",
  "result": {
    "ok": false,
    "error": {
      "code": "NO_SEMANTIC_SOURCE",
      "message": "No accessible UI source available; set cache policy to cache_only for offline replay",
      "recovery": ["see --semantic --visual --once --approval-token <token>", "see --semantic --refresh"]
    }
  },
  "safety_state": { "state": "BLOCKED", "code": "NO_SOURCE", "reason": "blocked" }
}
```

## 4) CLI contract: `peekxd see --semantic`

Signature:

`peekxd see --semantic [OPTIONS]`

Flags:

- `--json` (emit only JSON envelope)
- `--pretty` (pretty JSON)
- `--hud` (default: true, suppressed by `--json`)
- `--app <substring>` or `--window-id <id>`
- `--cache-policy <prefer_live|live_only|cache_only|refresh>`
- `--ttl <seconds>` (default 30)
- `--max-elements <n>`
- `--cache-only` (same as `--cache-policy cache_only`)
- `--refresh` (same as `--cache-policy refresh`)
- `--visual` (request evidence capture)
- `--once` (must be true if `--visual` is true)
- `--approval-token <token>` (required if `--visual`)
- `--visual-timeout <seconds>` (default 20)

Rules:

- `--visual` requires both `--once` and `--approval-token`.
- `--cache-only` with no fresh cache returns `NO_CACHED_STATE` and does not capture.
- `--refresh` bypasses cache and attempts live source.
- `--fields` optional field filter for JSON responses.

## 5) Terminal rendering examples

Default HUD (`--hud`):

```text
$ peekxd see --semantic --app firefox
snapshot=snap_20260529_9wz2qv1h6k source=live_accessibility ttl=30s cache=fresh
window=W1 focused app=firefox title="Peekxd docs"
elements=14 shown=5 actionable=4
W1-B3 button enabled  "Search"   @ (1240,18) 38x24
W1-I2 text    value="http://localhost" @ (112,80) 520x22
W1-B6 button enabled  "Bookmarks" @ (40,18) 72x24
```

JSON:

```text
$ peekxd see --semantic --json --pretty
{ "schema_version": "peekxd.see.v1", "result": {"ok": true}, "snapshot": { ... } }
```

Visual enabled (must be approved):

```text
$ peekxd see --semantic --visual --once --approval-token user:ops-abc123 --visual-timeout 20
snapshot=snap_20260529_aa2q3r1d9v source=live_accessibility visual=enabled once=true
visual_capture=~/cache/peekxd/visual_aa2q3r1d9v.png
```

## 6) MCP contract

### 6.1 Tool: `peekxd_see_semantic`
Input:

```json
{"app_name":"firefox","window_id":null,"cache_policy":"prefer_live","ttl_seconds":30,"max_elements":60,"visual":false,"visual_once":false}
```

Output: same envelope as section 3.

### 6.2 Tool: `peekxd_click_on`
Input:

```json
{"snapshot_id":"snap_20260529_9wz2qv1h6k","element_id":"W1-B3","button":"left","plan_only":true}
```

Output:

```json
{"ok":true,"plan_id":"plan_20260529_8h2","action":"click","snapshot_id":"snap_20260529_9wz2qv1h6k","element_id":"W1-B3","plan_only":true}
```

### 6.3 Tool: `peekxd_type_on`

```json
{"snapshot_id":"snap_20260529_9wz2qv1h6k","element_id":"W1-I2","text":"example","clear_first":true,"plan_only":true}
```

### 6.4 Tool: `peekxd_snapshot_get`

```json
{"snapshot_id":"snap_20260529_9wz2qv1h6k","include_elements":true}
```

Invalid ID output (shared by MCP actions):

```json
{"ok":false,"code":"INVALID_ELEMENT_ID","snapshot_id":"snap_20260529_...","element_id":"W1-B99","message":"Element missing in snapshot","suggestions":["see --semantic --refresh","peekxd_snapshot_get"]}
```

## 7) Cached state

State machine:

- `MISS` → no matching cache entry
- `FRESH` → cache entry with TTL not expired
- `STALE` → TTL expired but still available if policy allows fallback
- `REJECTED` → stale and policy `cache_only`

Cache behavior:

- cache key: hash(app/window/filter/schema version)
- default TTL: 30s
- invalidation events: focus change, window list change, successful action on element, manual cleanup
- include in response: `meta.cache_hit`, `snapshot.cached`, `meta.cache_ttl_remaining_seconds`

## 8) Safety states and failure codes

States:

- `OK`
- `OK_CACHED`
- `NO_SOURCE`
- `VISUAL_GATE_REQUIRED`
- `VISUAL_GATE_DENIED`
- `INVALID_SNAPSHOT`
- `INVALID_ELEMENT`
- `STALE` (snapshot existed but element/action context expired)

Codes:

- `NO_SEMANTIC_SOURCE`
- `NO_CACHED_STATE`
- `CACHE_ONLY_BLOCKED`
- `VISUAL_GATE_MISSING_TOKEN`
- `VISUAL_GATE_MISSING_ONCE`
- `INVALID_ELEMENT_ID`
- `STALE_ELEMENT`

Every failure response includes both `safety_state.state` and `error.code`.

## 9) Migration: screenshot-first -> semantic-first

Mapping:

- `peekxd see capture` -> `peekxd see --semantic`
- `peekxd mark_elements` -> `peekxd see --semantic --json`
- `peekxd find_and_click "X"` -> `peekxd_see_semantic` + `peekxd_click_on`
- MCP `find_and_click` -> `peekxd_click_on` (preferred), `peekxd_find_element` becomes compatibility alias

Migration steps:

1. Keep old commands available as wrappers, add deprecation warning.
2. Add `--semantic` contract as default output for any new see/inspect paths.
3. Add MCP `peekxd_see_semantic`, `peekxd_click_on`, `peekxd_type_on`, `peekxd_snapshot_get`.
4. Require `--visual --once` for any evidence capture.
5. Publish deprecation schedule after two releases.

## 10) Non-goals

- HTTP MCP transport work
- Visual replay pipeline
- Full daemon / background watcher

## 11) Acceptance checks

- `peekxd see --semantic` always includes `snapshot_id`.
- All element actions require `snapshot_id` + `element_id`.
- `--visual` rejects without `--approval-token` and `--once`.
- Stale cache path emits explicit warning state and guidance.
- MCP and CLI payloads remain schema-compatible (`peekxd.see.v1`).
