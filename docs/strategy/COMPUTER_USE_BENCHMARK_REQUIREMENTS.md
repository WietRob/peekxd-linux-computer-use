# Computer-use benchmark requirements for PeekXD

Status: draft v0.1, semantic-first and no-disturbance policy
Date: 2026-06-01

## Intent

Define what PeekXD must support before we can honestly call it benchmark-capable against OSWorld-style computer-use agents and product references such as Peekaboo v3, Claude Computer Use, Codex Computer Use, and Kimi Agent/Agent Swarm.

This document separates:

1. benchmark requirements,
2. competitor/reference capabilities,
3. current PeekXD evidence,
4. gap assessment,
5. Kanban work plan.

## Non-negotiable local policy

For this user and host, background screenshot/portal capture is disallowed because it visibly disturbs the live desktop. Benchmark work must be semantic-first by default:

- no `xdg-desktop-portal` screenshot prompts in background loops,
- no `doctor --smoke` pixel capture,
- no screenshot MCP tools by default,
- no live click/type/move unless explicitly approved,
- safe observation via accessibility/window state first,
- fail closed when semantic state is insufficient.

This means PeekXD may not be OSWorld-style benchmark-capable yet, because many public desktop CUA harnesses assume screenshot observations. That is a product/benchmark positioning constraint, not a reason to re-enable disturbing capture.

## Benchmark families and what they require

### OSWorld / OSWorld-Verified

Sources found:

- OSWorld describes real computer environments across Ubuntu, Windows, and macOS with 369 desktop/web/file/workflow tasks and execution-based evaluation.
- Epoch AI summary describes agents using keyboard/mouse primitives and structured observations such as accessibility trees.
- OSWorld-Human / OSWorld-Gold emphasize step efficiency and latency, not only success rate.

Required capabilities:

- reproducible VM/container environment,
- reset/setup scripts per task,
- observation channel: screenshots and/or structured accessibility trees,
- action channel: click, type, key, scroll, drag, wait,
- end-state validators,
- trajectory logging,
- latency/step counting,
- deterministic crash recovery,
- no uncontrolled real-user desktop side effects.

Semantic-first implication:

- If the harness accepts accessibility-tree observations, PeekXD can target that lane.
- If the harness requires pixel screenshots, current no-screenshot PeekXD is not compatible until we provide a non-disturbing benchmark-only capture backend inside an isolated VM, not on the user's live desktop.

### ScreenSpot / UI element grounding style benchmarks

Requirements:

- map natural-language target to UI element,
- output coordinates or element ID,
- require bounding boxes / center points,
- evaluate hit accuracy.

Semantic-first implication:

- We need stable element IDs and bounds/centers from AT-SPI/window providers.
- Current semantic smoke produced many `None` ids/bounds, so this is not ready.

### WebArena / browser/web navigation

Requirements:

- browser state observation,
- click/type/scroll/navigation,
- long-horizon task execution,
- instruction hierarchy / prompt injection resistance,
- success validators.

Semantic-first implication:

- Better served via browser automation/DOM/CDP than screenshots.
- PeekXD should integrate semantic browser/DOM observations where available, and use desktop actions only for shell/browser chrome gaps.

### AndroidWorld-style mobile GUI benchmarks

Out of scope for PeekXD Linux desktop unless we add Android emulator/device adapters.

## Reference products/capabilities

### Peekaboo v3 / current v3.x reference

Source: GitHub openclaw/Peekaboo extraction.

Capabilities reported:

- macOS-only, macOS 15+,
- CLI + optional MCP server,
- high-fidelity screen capture,
- AI visual analysis,
- `see` returns snapshot + element IDs,
- `click --on <id/query>` and coordinate click,
- menu listing/clicking,
- type/press/hotkey,
- scroll/swipe/drag,
- window/app/screen/menu listing,
- accessibility-specific `set-value` and `perform-action`,
- native agent flows and multi-screen automation.

Benchmark lesson:

- The key product pattern is not just screenshot. It is `see -> snapshot id -> element ids -> action on ids`.
- PeekXD should copy the architecture pattern, not the disturbing screenshot dependency.

### Claude Computer Use

Source: Anthropic docs extraction.

Capabilities reported:

- beta API tool,
- screenshot observation,
- mouse move/click/drag,
- keyboard typing/shortcuts,
- agent loop where model asks for tool actions and client executes,
- can combine with bash/text-editor/custom tools,
- security guidance: dedicated VM/container, no sensitive data, domain allowlists, human confirmation for consequential actions,
- prompt-injection risk from screenshots/web content,
- recommended XGA-ish display sizing in ecosystem docs.

Benchmark lesson:

- Claude-style benchmark readiness means an agent loop with screenshot/observation returns after each action.
- For live user desktop, this is too invasive unless isolated. For a benchmark VM, it is acceptable.

### OpenAI Codex Computer Use

Source: OpenAI Codex app docs extraction.

Capabilities reported:

- macOS Codex app computer-use plugin,
- screen recording + accessibility permissions,
- only allowed apps can be used,
- task starts by mentioning @Computer or @App,
- recommends structured integrations or in-app browser first,
- intended for scoped GUI tasks, app testing, browser flows, settings, GUI-only bugs,
- can continue locked/background use if explicitly enabled.

Benchmark lesson:

- Scoped app permissions and structured-integration-first are important. PeekXD should expose per-app/session allowlists before any action.
- Codex is not simply a raw screenshot tool; it has app-level approval semantics.

### Kimi K2.5 Agent / Agent Swarm

Source: Kimi K2.5 blog extraction.

Capabilities reported:

- native multimodal model trained on mixed visual/text tokens,
- K2.5 Agent and Agent Swarm beta modes,
- self-directed swarm up to 100 sub-agents and up to 1,500 tool calls,
- claims faster parallel execution for complex workflows,
- strong coding+vision, image/video-to-code, visual debugging,
- office productivity workflows.

Benchmark lesson:

- Kimi's contribution is orchestration and long-horizon tool-use parallelism, not necessarily a desktop driver API.
- For PeekXD, this maps to Kanban/swarm orchestration around a safe computer-use backend.

## Current PeekXD state from local evidence

Recent verified local evidence:

- Screenshot provider family removed/fail-closed by default.
- CLI capture commands fail closed:
  - `capture screen`: rc=1, removed message,
  - `capture window`: rc=1,
  - `capture region`: rc=1,
  - `see capture`: rc=1.
- `doctor --capability screenshot --smoke` reports `BLOCKED via removed` and does not capture.
- Full test suite: 441 passed.
- Semantic smoke:
  - `schema_version = peekxd.see.v1`,
  - `safety_state = OK / SEMANTIC_OK`,
  - `reason = live_accessibility_success`,
  - 3 windows,
  - 60 elements,
  - no screenshot/capture processes after run.

Weakness from semantic smoke:

- top-level fields are present, but many windows/elements had missing `id`, `bounds`, `active`, or `app`,
- many elements are app-level nodes rather than actionable controls,
- no verified element-ID click flow,
- no benchmark harness adapter,
- no isolated VM capture mode,
- no ScreenSpot-style coordinate grounding acceptance gate.

## Requirement matrix

| Area | Needed for benchmark capability | Current PeekXD state | Verdict |
|---|---|---|---|
| Safe observation | non-disturbing snapshot channel | semantic snapshot works | partial |
| Pixel screenshots | required by many CUA agents/harnesses | removed on live desktop | not live-desktop capable; needs isolated benchmark backend |
| Accessibility tree | structured UI state | works but raw/coarse | partial |
| Stable element IDs | click/type by id | implemented directionally, smoke showed ids None in sample | weak |
| Bounds/centers | target grounding | many bounds None | weak |
| Action primitives | click/type/key/scroll/drag/wait | present historically, not revalidated after screenshot removal | unknown / gated |
| Action safety | approval, app allowlist, deny zones | zones exist, but need screenshot-free audit semantics | partial |
| Agent loop | observe -> think -> act -> observe | orchestrator patched semantic-first | needs integration tests |
| MCP surface | tool registration for agents | semantic-first MCP exists | partial; needs profile tests |
| Benchmark reset | deterministic environment reset | absent | missing |
| Validators | task success checks | absent | missing |
| Trajectory logs | actions/observations/timing | audit exists | partial |
| Efficiency metrics | step/time/calls vs OSWorld-Human | absent | missing |
| Prompt injection defense | handle malicious screen/web text | mostly absent | missing |
| Browser DOM mode | structured web alternative | absent | missing |
| Isolated VM mode | benchmark-capable screenshots without disturbing user | absent | missing |

## Initial conclusion

PeekXD is currently safe-semantic-prototype capable, not benchmark-capable against full screenshot-based OSWorld-style agents.

The right benchmark path is split:

1. Live desktop mode: semantic-first, no screenshots, no user disturbance.
2. Benchmark VM mode: optional isolated screenshot backend, allowed only inside disposable VM/container harness.
3. Browser mode: DOM/CDP-first, not screenshot-first.
4. Element-ID control mode: stable IDs + bounds + action-on-id before claiming parity with Peekaboo v3.

## Kanban workstreams to create

1. Requirements lane: formalize benchmark acceptance gates and compare OSWorld/ScreenSpot/WebArena.
2. Inventory lane: audit current PeekXD capabilities and generate evidence matrix from code/tests only.
3. Architecture lane: design dual-mode architecture: live semantic-safe mode vs isolated benchmark visual mode.
4. Roadmap lane: map Peekaboo v3 / Claude / Codex / Kimi references into a staged PeekXD roadmap.
5. Review lane: challenge benchmark-capability claims and produce a no-hype readiness statement.
