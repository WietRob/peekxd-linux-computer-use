# Computer-Use Benchmark Architecture (PeekXD)

Status: Draft architecture/spec only — do not implement or re-enable live screenshots from this document.
Date: 2026-06-01
Inputs:
- `docs/strategy/COMPUTER_USE_BENCHMARK_REQUIREMENTS.md`
- `docs/strategy/COMPUTER_USE_BENCHMARK_ACCEPTANCE_GATES.md`
- `docs/requirements/SEMANTIC_COMPUTER_USE_REQUIREMENTS.md`
- `docs/requirements/PEEKXD_SEMANTIC_SEE_CONTRACT.md`

## 1. Goal

PeekXD needs a benchmark-capable architecture without violating the live-host no-disturbance policy. The design is a multi-mode computer-use stack with explicit isolation boundaries:

1. **Live semantic-safe mode**: default for this host and normal agent/operator use. It observes only semantic state and fails closed when semantic state is insufficient.
2. **Isolated benchmark VM visual mode**: optional benchmark-only mode for OSWorld/ScreenSpot-style protocols that require pixels. It is allowed only inside a disposable benchmark environment, never on the user's live desktop.
3. **Browser DOM mode**: structured web automation mode for WebArena-like tasks. It uses DOM/CDP/browser accessibility state instead of screenshots.
4. **Action-on-element-id mode**: shared control contract where every targetable action resolves through `snapshot_id` + `element_id` provenance before execution.

This is a design/spec artifact. It intentionally does not run live screenshots, MCP tools, click/type/move, or benchmark episodes.

## 2. Non-negotiable policy

### 2.1 Default deny for live visual capture

In live host mode, these remain forbidden:

- portal screenshot prompts,
- PipeWire/ScreenCast sessions,
- background screenshot loops,
- `doctor --smoke` pixel capture,
- MCP screenshot/capture tools,
- visual capture fallback after semantic failure,
- live click/type/move actions without explicit approval.

A missing semantic observation is not a reason to fall back to pixels on the live desktop. It is a structured blocked state.

### 2.2 Isolated visual exception

Visual capture is permitted only when all of these are true:

- `mode = isolated_visual`,
- the environment is a disposable VM/container/session created for the benchmark,
- the run has explicit user/operator consent and scope,
- no host desktop/session sockets are mounted into the benchmark runner,
- artifacts identify `observation_path = isolated-visual`,
- teardown/reset is deterministic.

### 2.3 Mode boundaries are security boundaries

Mode selection must be explicit, auditable, and monotonic within an episode. A live semantic run may not silently upgrade to isolated visual; it must end as blocked/unsupported and instruct the operator to start a separate isolated benchmark run.

## 3. Architecture overview

```text
                  +-------------------------------+
                  | Benchmark / Agent Controller  |
                  | OSWorld, ScreenSpot, WebArena |
                  +---------------+---------------+
                                  |
                                  v
                  +-------------------------------+
                  | PeekXD Harness Adapter        |
                  | episode API, scoring, logs    |
                  +---------------+---------------+
                                  |
        +-------------------------+--------------------------+
        |                         |                          |
        v                         v                          v
+---------------+        +-------------------+       +----------------+
| Observation   |        | Action Router      |       | Safety Policy  |
| Broker        |        | id -> plan -> exec |       | mode gates     |
+-------+-------+        +---------+---------+       +-------+--------+
        |                          |                         |
        |                          |                         |
        v                          v                         v
+-------+-------+       +----------+----------+       +------+---------+
| live_semantic |       | element-id actions |       | audit/approvals|
| isolated_vis  |       | browser actions    |       | allow/deny     |
| browser_dom   |       | VM-scoped actions  |       | redaction      |
+---------------+       +---------------------+       +----------------+
```

The adapter exposes one benchmark-facing episode interface and hides the mode-specific observation/action providers behind policy gates.

## 4. Modes

### 4.1 Live semantic-safe mode

Purpose: normal PeekXD operation on the user's real desktop.

Observation source order:

1. live accessibility/window providers,
2. fresh semantic cache,
3. explicit user-provided context for planning-only operations,
4. blocked state with diagnostic guidance.

Allowed observations:

- windows, titles, app IDs, focus state,
- accessibility roles/names/states,
- `snapshot_id`, `window_id`, `element_id`, bounds when provided by accessibility,
- semantic diffs between snapshots.

Forbidden observations:

- screenshots,
- image OCR,
- visual model calls on live desktop images,
- recurring capture/polling.

Allowed actions:

- plan-only action proposals by default,
- optional execute after explicit approval policy permits it,
- no action if `snapshot_id` or `element_id` is stale/invalid,
- no action when zone policy or app allowlist denies it.

Primary success condition:

- The mode is safe and honest. It can claim semantic benchmark readiness only for benchmarks that accept semantic observations. It cannot claim full OSWorld pixel benchmark readiness.

Failure shape:

```json
{
  "mode": "live_semantic_safe",
  "result": "blocked",
  "code": "SEMANTIC_INSUFFICIENT_NO_LIVE_VISUAL_FALLBACK",
  "observation_path": "semantic-only",
  "allowed_next_steps": ["refresh_semantic", "start_separate_isolated_visual_benchmark"]
}
```

### 4.2 Isolated benchmark VM visual mode

Purpose: compatibility with screenshot-required desktop GUI benchmarks such as OSWorld-style and ScreenSpot-style lanes.

Environment requirements:

- disposable VM/container or equivalent sandbox,
- benchmark-owned display server/session,
- no user desktop/session bus/portal exposure,
- deterministic snapshot/reset per task,
- benchmark-specific allowlists for apps, domains, filesystem paths, and network,
- bounded duration and resource limits.

Allowed observations:

- screenshots from the isolated display,
- accessibility/window tree from the isolated environment,
- optional OCR/vision over isolated screenshots,
- synchronized semantic+visual snapshots.

Forbidden observations:

- any host desktop visual capture,
- any host user's session bus/window tree unless intentionally passed as benchmark fixture,
- background capture outside the active episode.

Action scope:

- click/type/key/scroll/drag/wait only against the benchmark-owned display,
- file/network side effects constrained to benchmark fixture rules,
- destructive actions require benchmark policy classification and may be denied even in isolation.

Primary success condition:

- Supports benchmark protocols that require images while keeping the live desktop undisturbed.

Hard gate:

- If the runner cannot prove isolation, the mode must not start.

### 4.3 Browser DOM mode

Purpose: WebArena/browser-task compatibility without screenshot dependence.

Observation providers:

- URL/title/history,
- DOM tree with visible text/roles/labels,
- browser accessibility tree,
- active element and form state,
- console/network diagnostics when permitted,
- optional isolated visual snapshot only when a benchmark explicitly requires it and isolated mode is active.

Actions:

- navigate,
- click by DOM/accessibility element id,
- type/fill/select,
- key/scroll,
- wait for selector/text/network-idle,
- tab/session management.

Safety boundaries:

- origin allowlist/denylist per episode,
- prompt-injection classification for page content,
- no cross-origin side effects unless the benchmark task explicitly scopes them,
- no credential or personal browser profile reuse.

This mode should be preferred for WebArena-like tasks because it is more deterministic than visual desktop control and avoids live screenshot disturbance.

### 4.4 Action-on-element-id mode

Purpose: make PeekXD's control model match the useful product pattern from Peekaboo-style `see -> id -> act on id`, without depending on screenshots.

All element-targeted actions use this minimum contract:

```json
{
  "mode": "live_semantic_safe | isolated_visual | browser_dom",
  "snapshot_id": "snap_YYYYMMDD_xxxxxxxxxx",
  "element_id": "W1-B3",
  "action": "click | type | key | scroll | drag | wait",
  "plan_id": "plan_YYYYMMDD_xxxxxxxxxx",
  "plan_only": true,
  "approval": {
    "required": true,
    "scope": "live_host | benchmark_vm | browser_sandbox"
  }
}
```

Execution requirements:

- resolve `snapshot_id`,
- resolve `element_id` within that snapshot only,
- verify element role/action compatibility,
- verify bounds/center if pointer action is needed,
- verify snapshot freshness or require refresh,
- verify mode policy and zone/app/origin allowlists,
- produce an audit event before and after execution.

Invalid IDs fail closed:

```json
{
  "ok": false,
  "code": "INVALID_ELEMENT_ID",
  "snapshot_id": "snap_...",
  "element_id": "W1-B99",
  "suggestions": ["refresh_semantic", "inspect_snapshot"]
}
```

## 5. Core components

### 5.1 Mode manager

Responsibilities:

- parse explicit mode selection,
- reject implicit visual upgrades,
- expose mode to all observations/actions/logs,
- enforce mode compatibility with environment proof,
- freeze mode for an episode after first observation.

Suggested enum:

- `live_semantic_safe`,
- `isolated_visual`,
- `browser_dom`,
- `plan_only`.

### 5.2 Observation broker

Responsibilities:

- normalize observations from semantic, isolated visual, and browser DOM providers,
- emit one schema envelope with `observation_path`, `source_fidelity`, and `mode`,
- attach visual artifacts only when mode policy allows,
- mark all observations with provenance and timing.

Provider interfaces:

```python
class ObservationProvider:
    mode: ComputerUseMode
    def observe(self, request: ObservationRequest) -> ObservationEnvelope: ...
    def supports(self, capability: str) -> bool: ...
```

Required normalized fields:

- `episode_id`,
- `step_id`,
- `mode`,
- `observation_path`,
- `snapshot_id`,
- `created_at`,
- `windows`,
- `elements`,
- `visual_artifact` only for isolated visual,
- `browser_state` only for browser mode,
- `safety_state`,
- `result`.

### 5.3 Snapshot store

Responsibilities:

- retain semantic and optional isolated visual snapshots per episode,
- enforce TTL and same-mode lookup,
- map `snapshot_id` + `element_id` to provider-native targets,
- support offline benchmark trace replay,
- avoid leaking host paths or sensitive values in IDs.

Rules:

- IDs are snapshot-local except `snapshot_id`,
- stale snapshots cannot execute actions without policy-approved refresh,
- visual artifacts are never stored for live mode because live visual artifacts cannot exist.

### 5.4 Action router

Responsibilities:

- accept benchmark/agent action requests,
- validate target IDs and role/action compatibility,
- convert semantic/browser targets into provider-native operations,
- produce plan-preview-execute records,
- enforce idempotency and replay protections.

Action stages:

1. `PLAN`: no side effects, validates target and creates `plan_id`.
2. `PREVIEW`: deterministic summary for operator/controller.
3. `APPROVE`: policy or human approval attaches scope token.
4. `EXECUTE`: side-effect action in allowed mode/scope.
5. `OBSERVE_AFTER`: follow-up observation and delta.

### 5.5 Safety policy engine

Responsibilities:

- centralize mode gates,
- validate isolation proof,
- apply live-host no-visual invariant,
- apply app/window/origin allowlists,
- apply deny zones and destructive-action classes,
- require approvals for side effects,
- generate stable block codes for benchmarks.

Policy decisions are data, not exceptions:

```json
{
  "allowed": false,
  "code": "LIVE_VISUAL_CAPTURE_FORBIDDEN",
  "reason": "live_semantic_safe mode cannot request screenshots",
  "required_mode": "isolated_visual"
}
```

### 5.6 Audit and trajectory logger

Responsibilities:

- write benchmark-compatible JSONL trajectory logs,
- include step/action timing and return codes,
- distinguish blocked safety failures from task failures,
- include observation path and mode on every row,
- produce acceptance-gate summary artifacts.

Minimum event types:

- `episode_start`,
- `observe`,
- `plan_action`,
- `approval_required`,
- `approval_granted`,
- `execute_action`,
- `observe_after`,
- `validator_result`,
- `episode_end`.

## 6. Benchmark harness adapter

### 6.1 Adapter purpose

The harness adapter translates external benchmark protocols into PeekXD episodes without exposing benchmark code to unsafe live host primitives.

Responsibilities:

- create/reset benchmark environment,
- select mode explicitly,
- expose observations in the protocol's expected shape,
- translate benchmark actions into PeekXD action plans,
- run validators,
- emit score/trajectory artifacts,
- fail closed when mode requirements cannot be met.

### 6.2 Episode lifecycle

```text
prepare_environment
  -> prove_mode_safety
  -> reset_task
  -> observe_initial
  -> loop:
       receive_agent_action
       plan_action
       policy_check
       execute_or_block
       observe_after
       validate_if_needed
  -> finalize_score
  -> teardown_or_restore_snapshot
```

### 6.3 Adapter output contract

```json
{
  "run_id": "bench_20260601_abcdef",
  "family": "osworld_verified | osworld_human | screenspot | webarena",
  "task_id": "external-task-id",
  "mode": "live_semantic_safe | isolated_visual | browser_dom",
  "observation_path": "semantic-only | isolated-visual | browser-dom | semantic-then-isolated-visual | not-completed",
  "gate_status": "PASS | CONDITIONALLY_PASS | FAIL",
  "success": false,
  "blocked": true,
  "block_code": "SEMANTIC_INSUFFICIENT_NO_LIVE_VISUAL_FALLBACK",
  "steps": 0,
  "elapsed_ms": 0,
  "tool_calls": 0,
  "artifacts": {
    "trajectory_jsonl": "...",
    "score_json": "...",
    "audit_jsonl": "..."
  },
  "must_ok": false,
  "should_ok": false,
  "could_ok": false,
  "blockers": [
    "isolated visual backend missing for screenshot-required tasks"
  ],
  "notes": [
    "live mode did not request screenshots"
  ]
}
```

### 6.4 Benchmark-family mapping

| Family | Preferred mode | Visual requirement | Adapter stance |
|---|---|---:|---|
| OSWorld / OSWorld-Verified | isolated_visual when screenshots required; live_semantic_safe only for semantic-compatible tasks | often yes | Red until isolated VM runner + reset + validators exist |
| OSWorld-Human / Gold | same as OSWorld plus efficiency telemetry | often yes | Requires step/time/cost metrics in trajectory logs |
| ScreenSpot-style grounding | live_semantic_safe for semantic ID/bounds benchmarks; isolated_visual for pixel hit tests | sometimes yes | Requires complete ID + bounds + hit/miss evaluator |
| WebArena | browser_dom | no by default | Prefer DOM/CDP; isolated visual only for visual-only tasks |

## 7. Safety and approval boundaries

### 7.1 Read-only vs mutation boundaries

Read-only observations:

- live semantic observations are allowed by default,
- browser DOM observations are allowed in benchmark/browser sandbox,
- isolated visual observations are allowed only in isolated benchmark mode.

Mutation-capable actions:

- default to `plan_only`,
- require target provenance,
- require policy approval,
- require app/window/origin scope,
- require audit before execution.

### 7.2 Consequential action classes

Actions should be classified before execution:

- `low`: local UI navigation, no data mutation,
- `medium`: form entry, file changes inside benchmark sandbox,
- `high`: network submission, deletion, irreversible settings change,
- `forbidden`: host-desktop capture in live mode, credentials exfiltration, out-of-scope domains/apps.

Benchmarks may auto-approve low/medium inside isolated fixtures but must still log scope. Live host mode should not auto-execute mutation from a benchmark adapter.

### 7.3 Isolation proof checklist

Before `isolated_visual` starts, the runner must record:

- benchmark display identifier,
- VM/container/session id,
- reset snapshot id or image digest,
- no host display/session socket exposure,
- app/domain/filesystem allowlists,
- artifact directory,
- teardown command,
- consent/scope metadata.

If any item is missing, return `ISOLATION_PROOF_MISSING` and do not capture.

## 8. Implementation plan

> For Hermes: Use subagent-driven-development skill to implement this plan task-by-task after human review. This task is design/spec only; do not implement from this run.

### Task 1: Add mode model and policy-only tests

Objective: introduce explicit mode names and policy decisions without enabling new providers.

Files:
- Create: `peekxd/computer_use/modes.py`
- Create: `tests/test_computer_use_modes.py`

Test cases:
- live mode rejects visual capture capability,
- isolated visual rejects start without isolation proof,
- browser DOM rejects screenshot requirement unless isolated visual bridge is explicit,
- mode cannot change from live semantic to isolated visual mid-episode.

Verification:
- `pytest tests/test_computer_use_modes.py -v`

### Task 2: Add observation envelope schema

Objective: normalize semantic/browser/isolated observations with mode and observation-path fields.

Files:
- Create: `peekxd/computer_use/observation.py`
- Create: `tests/test_computer_use_observation.py`
- Modify later: `peekxd/semantic.py` only to map existing semantic output into the new envelope, not to capture visuals.

Test cases:
- live semantic envelope has no visual artifact field,
- isolated visual envelope may include visual artifact metadata,
- every envelope includes `mode`, `observation_path`, `snapshot_id`, `safety_state`, and `result`.

Verification:
- `pytest tests/test_computer_use_observation.py -v`

### Task 3: Add snapshot store for element-id resolution

Objective: make `snapshot_id` + `element_id` the shared target resolution primitive.

Files:
- Create: `peekxd/computer_use/snapshots.py`
- Create: `tests/test_computer_use_snapshots.py`

Test cases:
- valid element resolves only in its own snapshot,
- stale snapshot returns `STALE_SNAPSHOT`,
- unknown element returns `INVALID_ELEMENT_ID`,
- live snapshots cannot contain visual artifacts.

Verification:
- `pytest tests/test_computer_use_snapshots.py -v`

### Task 4: Add action planning/router interfaces

Objective: implement plan-only action routing before any execution provider integration.

Files:
- Create: `peekxd/computer_use/actions.py`
- Create: `tests/test_computer_use_action_router.py`

Test cases:
- `click` on valid element creates plan with `plan_only=true`,
- invalid role/action compatibility blocks,
- missing approval blocks execution,
- duplicate plan execution is suppressed.

Verification:
- `pytest tests/test_computer_use_action_router.py -v`

### Task 5: Add browser DOM provider abstraction

Objective: define a DOM/CDP-backed observation/action provider contract without binding to screenshots.

Files:
- Create: `peekxd/computer_use/browser.py`
- Create: `tests/test_computer_use_browser_contract.py`

Test cases:
- browser observation emits URL/title/DOM/accessibility fields,
- click/type map through DOM element ids,
- origin denylist blocks actions,
- visual snapshot request is denied outside isolated visual bridge.

Verification:
- `pytest tests/test_computer_use_browser_contract.py -v`

### Task 6: Add isolated visual adapter interface without implementation

Objective: define the benchmark-only visual interface and fail closed until isolation proof exists.

Files:
- Create: `peekxd/computer_use/isolated_visual.py`
- Create: `tests/test_computer_use_isolated_visual_policy.py`

Test cases:
- no isolation proof returns `ISOLATION_PROOF_MISSING`,
- host display/session socket paths are rejected,
- valid fake proof allows provider construction in tests only,
- capture is never reachable from live semantic mode.

Verification:
- `pytest tests/test_computer_use_isolated_visual_policy.py -v`

### Task 7: Add benchmark harness adapter skeleton

Objective: expose an episode lifecycle that can return blocked/unsupported results today and later wrap OSWorld/WebArena adapters.

Files:
- Create: `peekxd/benchmark/adapter.py`
- Create: `tests/test_benchmark_adapter.py`

Test cases:
- screenshot-required OSWorld task in live mode returns `FAIL` with live visual fallback forbidden,
- WebArena task selects browser DOM mode,
- ScreenSpot semantic task requires element bounds,
- output contract includes gate fields from acceptance matrix.

Verification:
- `pytest tests/test_benchmark_adapter.py -v`

### Task 8: Wire audit/trajectory records

Objective: produce benchmark-compatible JSONL events while preserving safety provenance.

Files:
- Create: `peekxd/benchmark/trajectory.py`
- Create: `tests/test_benchmark_trajectory.py`

Test cases:
- every event includes `run_id`, `episode_id`, `step_id`, `mode`, `observation_path`, and timestamp,
- blocked policy decisions are distinct from task validation failure,
- final score JSON includes steps/elapsed/tool_calls/gate_status.

Verification:
- `pytest tests/test_benchmark_trajectory.py -v`

### Task 9: Integrate with CLI/MCP only after policy tests pass

Objective: expose new contracts without changing safe defaults.

Files:
- Modify: `peekxd/cli.py`
- Modify: `peekxd/mcp_server/server.py`
- Modify: `tests/test_cli.py`
- Modify: `tests/test_mcp.py`

Test cases:
- default CLI/MCP remains semantic-first,
- no screenshot/capture tools are registered in live mode,
- benchmark adapter commands require explicit mode and fail closed by default,
- `--isolated-visual` requires proof path/scope and never uses host desktop.

Verification:
- targeted CLI/MCP tests plus full suite.

## 9. Acceptance criteria for this architecture

This architecture is acceptable when future implementation can demonstrate:

1. Live semantic-safe mode has no path to screenshots or visual capture fallback.
2. Isolated visual mode cannot start without machine-checkable isolation proof.
3. Browser DOM mode handles WebArena-style observations/actions without screenshots.
4. All element actions require `snapshot_id` + `element_id` provenance.
5. Invalid/stale targets fail closed with structured recovery guidance.
6. Benchmark adapter outputs include mode, observation path, gate status, blockers, trajectory, score, and audit artifacts.
7. OSWorld/ScreenSpot/WebArena readiness claims map to the acceptance-gate matrix and do not overstate unsupported screenshot-required lanes.
8. Any code integration starts with policy/schema tests before provider implementation.

## 10. Open decisions

1. Which VM/container runner should be the first isolated visual backend: QEMU/KVM, Docker+Xvfb, Firecracker, or external OSWorld runner?
2. What is the minimum machine-checkable isolation proof for the first implementation?
3. Should browser DOM mode live under PeekXD directly or integrate through an existing browser automation library as an optional provider?
4. What retention policy should benchmark visual artifacts use to avoid storing sensitive data longer than needed?
5. How should semantic bounds quality be scored for ScreenSpot-style tasks when accessibility providers return incomplete geometry?

## 11. Current readiness statement

PeekXD should be described as **semantic-safe prototype capable** today, not full benchmark-capable. The path to credible benchmark capability is:

- live semantic-safe benchmark lane for semantic-compatible tasks,
- isolated visual benchmark lane for pixel-required desktop tasks,
- browser DOM lane for WebArena-style tasks,
- action-on-element-id and trajectory logging across all lanes.

Until isolated visual mode, reset lifecycle, validators, stable element IDs/bounds, and benchmark adapter outputs exist, OSWorld/ScreenSpot/WebArena claims should remain Red or Yellow according to `COMPUTER_USE_BENCHMARK_ACCEPTANCE_GATES.md`.
