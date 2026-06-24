# Computer-Use Benchmark Acceptance Gates (PeekXD)

Status: Draft — planning/research lane only (no live actions, no screenshot/MCP capture)
Date: 2026-06-01
Source baseline: docs/strategy/COMPUTER_USE_BENCHMARK_REQUIREMENTS.md

## Scope and hard constraints

This matrix formalizes what must/should/could be satisfied for each benchmark family in planning and acceptance decisions for PeekXD.

## Global hard policy (applies to all families)

- **Hard NO-GO:** No live desktop screenshot capture in normal worker execution.
- **Allowed exception:** Visual capture is allowed **only** in an explicit **benchmark-isolated mode** (disposable VM/container, consented scope, bounded duration).
- **Forbidden in live host mode:**
  - portal screenshot API loops,
  - recurring image capture daemons,
  - background screen polling,
  - any benchmark attempt that depends on live host images without explicit approval and isolation.
- **Failure mode:** If observation is insufficient in live mode, benchmark adapters must fail closed and continue with semantic diagnostics.
- **Artifact rule:** All benchmark artifacts must include observation path: `semantic-only`, `isolated-visual`, or `not-completed`.

## Acceptance matrix

Legend:
- **Must** = required for any claim of benchmark-readiness.
- **Should** = strongly recommended for credible release quality.
- **Could** = optional/enhancement paths once Must and Should are met.

### OSWorld / OSWorld-Verified

| Area | Must | Should | Could |
|---|---|---|---|
| Observation contract | Deterministic task environment provides required semantic state (windows/app/element tree) at each step. | Optional screenshot channel is available in isolated-visual mode when benchmark protocol requires pixels. | Per-task adaptive observation fallback: semantic-first, then isolated-visual when policy allows. |
| Action primitives | Stable action channel for click/type/drag/scroll/key/wait in benchmark namespace. | Element-level action routing with stable references. | Action idempotency + replay guard for safety. |
| Episode lifecycle | Setup/reset pipeline per task with reproducibility and clean rollback. | Deterministic crash recovery with resumable task IDs. | Pre-warmed VM images and snapshot restore for faster reruns. |
| Evaluation hooks | End-state validator and pass/fail signal per task. | Full trajectory logs (action, observation source, timing, return codes). | Deterministic scoring artifacts (JSONL/CSV) with metadata provenance. |
| Safety and side effects | No user-desktop side effects outside benchmark scope. | Deny-lists/allow-lists and destructive-action guardrails. | Additional cgroup/cpu/memory/resource hardening in harness. |
| Performance | Per-task wall-clock and action-count telemetry. | Step-efficiency and throughput as first-class eval outputs. | SLA envelopes by task class (fast/normal/slow). |

### OSWorld-Human / OSWorld-Gold (efficiency)

| Area | Must | Should | Could |
|---|---|---|---|
| Score semantics | Report success with efficiency metrics (actions/task, elapsed, effective steps). | Compare against baseline trajectories where available. | Report repeated-run confidence intervals. |
| Planner behavior | Observable plan/eval loop to explain efficiency deltas. | Action compactness checks to avoid redundant navigation. | Cross-run route optimization and action deduplication. |
| Correctness | No silent fallback to unsupported observation mode. | Clear abort/blocked/retry reason codes in logs. | Offline trace replay for error analysis. |
| Cost accounting | Track model/tool-call budget per episode. | Maintain cost-normalized efficiency dashboards. | Cost-aware planning policy under equal-success conditions. |

### ScreenSpot-style grounding

| Area | Must | Should | Could |
|---|---|---|---|
| Grounding input | Stable element identity from semantic/accessibility source (`element_id` equivalent). | Bounding geometry for each actionable target (`bounds` / `center`). | Optional calibration dataset for edge widgets and non-standard controls. |
| Grounding quality | Target trace includes ID -> resolved role/name/path. | Hit/miss scoring on repeated grounding tasks (precision/recall buckets). | Heatmap of miss patterns by widget family. |
| Execution | Action path supports element-id or query targeting. | Fallback strategy when ID is missing (refresh tree or alternate targeting). | Pixel-grounding bridge only in isolated-visual benchmark mode. |
| Evaluation | Emit per-action outcome (`hit`, `miss`, `near miss`, `invalid target`). | Confidence-aware grounding thresholds. | Per-task grounding leaderboard over multiple benchmark runs. |

### WebArena / browser tasks

| Area | Must | Should | Could |
|---|---|---|---|
| Observation | Structured browser state (DOM/URL/title/active element + semantic metadata). | Optional accessibility tree for browser windows. | Visual snapshot only in explicit isolated-visual benchmark mode. |
| Actions | Deterministic click/type/scroll/navigation with bounded retries. | Strong prompt-injection handling for web content. | Multi-tab/session orchestration with preserved context state. |
| Evaluation | Task-level success predicate, not only string heuristics. | Step/time failure taxonomy (`blocked`/`timeout`/`wrong-nav`/`js-error`). | Cross-browser harness (Chromium baseline, optional extension to Firefox/WebKit). |
| Safety | No cross-origin side effects outside browser sandbox. | Explicit allow/deny origin policy per run. | CSP/injection hardening experiments tied to benchmark families. |

## Quick gate outcomes

- **Green:** all **Must** gates satisfied for that benchmark family.
- **Yellow:** all Must gates satisfied, one or more **Should** gates open.
- **Red:** one or more Must gates unresolved.

For this host, any family that requires pixel observation in the default path without an approved isolated-visual mode is **Red by policy**, even if all semantic gates pass.

## Recommended adapter output contract

- `family` = {`osworld_verified`, `osworld_human`, `screenspot`, `webarena`}
- `mode` = {`live_semantic_only`, `isolated_visual`}
- `observation_path` = {`semantic`, `semantic_then_isolated_visual`}
- `gate_status` = {`PASS`, `CONDITIONALLY_PASS`, `FAIL`}
- `must_ok`, `should_ok`, `could_ok` = booleans
- `blockers` = list of unresolved Must gates with owner/timebox
- `notes` = concise evidence links (test IDs, run IDs, logs)
