# linux-computer-use

> peekxd — Computer Use Skill for Linux (Hermes Agent Edition)
> Inspired by peekxd (Peter Steinberger) — ported from macOS to Linux

## Overview

peekxd gives AI agents **maximum power** over Linux desktops. It provides screenshot capture with AI-powered bounding box detection, mouse/keyboard control, UI inspection, window management, action sequences with wait/retry logic, a full See-Think-Act autonomous loop, safety guardrails, session memory, audit trails, and auto-cleanup — all through CLI, MCP server, or direct Python API.

## Installation

### Automatic (install.sh)

```bash
cd ~/.hermes/skills/linux-computer-use
./install.sh
```

### Manual

```bash
sudo apt-get install -y xdotool imagemagick grim ydotool python3-pyatspi2
pip install click pillow openai anthropic requests fastmcp pydantic
pip install -e ".[all]"
```

## Quick Start for Agents

### 1. Mark Elements (Most Powerful)

```bash
peekxd agent mark
# Returns numbered bounding boxes for ALL UI elements with coordinates
```

### 2. Run Autonomous Task

```bash
peekxd agent run "Open Firefox and navigate to github.com"
```

### 3. Get Tool Definitions (for LLM)

```bash
peekxd agent tools
# Returns JSON schema for all 14 available tools
```

## What's New in v0.3.0

### Softbox Ghost Mode (v0.3.1 — V1.1)
Risk-based zone system for safe desktop automation:
- **GHOST** — Preview only, no execution. Risky actions show as overlay/preview.
- **GUIDED** — Normal guardrails + audit (default for unknown safe actions).
- **DIRECT** — Direct execution for trusted low-risk actions (scroll, read-only).

### Softbox Shadow Mode (v0.3.2 — V2)
Before/after screenshot capture for normal UI-modifying actions:
- **SHADOW** — Execute with before/after snapshots + shadow audit metadata.
  type and click actions run in SHADOW zone when no risk factors are detected.
  Audit includes zone="shadow", executed=True, screenshot_before/after.
  No rollback. No live overlay.

### Softbox Ghost Live Overlay (v0.3.3 — V3)
Live overlay window for GHOST actions:
- **Tkinter overlay** shows action, risk factors, screenshot, approve/cancel buttons.
- **Timeout**: auto-cancels after configurable seconds (default: 5).
- **Noop fallback**: headless/CI environments use NoopOverlayBackend.
- GHOST remains non-executing even if user approves. V3 is preview-only overlay.
- Lazy imports: tkinter loaded only when overlay is shown.

### Softbox V4 — Confirmable Ghost Actions (v0.3.4)
Two-tier GHOST classification with conditional execution after overlay approval:

**Routing Architecture:** APPROVABLE_GHOST is reached via SHADOW zone, NOT the GHOST zone.
Safe actions (click, type) land in `Zone.SHADOW` via `ZoneDecision.decide()`. When both
overlay and approval-execution flags are enabled, SHADOW actions route through an overlay
confirmation flow instead of executing directly with before/after snapshots.

- **HARD_BLOCKED_GHOST** — Never executes, regardless of approval. GHOST zone actions
  (with risk factors) always hard-block.
- **APPROVABLE_GHOST** — SHADOW-zone actions with `risk_factors=[]` that may execute
  if the user approves via overlay.
- **`--ghost-approval-execution`** CLI flag enables the SHADOW-to-confirmable routing.
- Hard-blocked categories: destructive commands, credential input, protected paths,
  system key combos, unknown actions.
- Approvable categories: non-destructive SHADOW-zone actions (click, type, type_text)
  with ZERO risk factors.

```bash
peekxd agent run "TASK" --ghost-overlay --ghost-approval-execution  # Approved safe SHADOW actions execute
peekxd agent run "TASK" --ghost-overlay                              # SHADOW actions execute normally (V2 compat)
```

```bash
peekxd agent run "TASK" --ghost --ghost-overlay              # Force ghost + show overlay
peekxd agent run "TASK" --ghost-overlay --ghost-overlay-timeout 10  # Custom timeout
peekxd agent run "TASK" --ghost-overlay --ghost-overlay-backend noop  # Noop backend
```

```bash
peekxd agent run "TASK" --ghost              # Force all actions to preview only
peekxd safety zone click '{"x": 100, "y": 200}' # Returns SHADOW for safe clicks
peekxd safety zone type '{"text": "hello"}'     # Returns SHADOW for safe typing
```

Zone assignment (V2 → V4):
|| Action | Risk-Free Zone | V4 Confirmable Routing | With Risk Factors ||
||--------|---------------|------------------------|--------------------|
|| click  | SHADOW        | APPROVABLE_GHOST (via SHADOW, if flags on + approved) | GHOST → HARD_BLOCKED_GHOST |
|| type   | SHADOW        | APPROVABLE_GHOST (via SHADOW, if flags on + approved) | GHOST → HARD_BLOCKED_GHOST |
|| type_text | SHADOW     | APPROVABLE_GHOST (via SHADOW, if flags on + approved) | GHOST → HARD_BLOCKED_GHOST |
|| scroll | DIRECT        | —                      | — |
|| capture_screen | DIRECT | — (not SHADOW)       | GHOST → HARD_BLOCKED_GHOST |
|| key/hotkey | DIRECT    | — (not SHADOW)         | GHOST → HARD_BLOCKED_GHOST |
|| unknown action | GHOST  | — (risk factors)     | GHOST → HARD_BLOCKED_GHOST ||

Risk factors that trigger GHOST:
- Destructive commands (rm, sudo, dd, mkfs, etc.)
- Credential-like input (password, token, key)
- Protected paths (/etc, /sys, /home, etc.)
- Unknown action types
- Shell metacharacters

### Safety Guardrails (v0.3.0)
Three safety levels protect against destructive actions:
- **strict** — Preview mode, no real actions executed
- **normal** — Blocks destructive commands (rm, sudo, dd, mkfs, etc.)
- **permissive** — Minimal checks, execute directly

```bash
peekxd agent run "TASK" --safety strict       # Simulation only
peekxd agent run "TASK" --safety normal       # Block destructive (default)
peekxd safety check type '{"text": "rm -rf /"}'  # Test if blocked
peekxd safety preview click '{"x": 100, "y": 200}' # Dry-run
```

### Session Memory (v0.3.0)
Element positions are cached across actions. The agent remembers where the "Submit button" was and reuses coordinates instead of calling vision again.

### Audit Trail (v0.3.0)
Every action is logged with timestamp, parameters, and result. Exportable as JSON.

```bash
peekxd audit show                    # Human-readable trail
peekxd audit export                  # JSON export
peekxd audit summary                 # Session statistics
```

### Auto-Cleanup (v0.3.0)
Old screenshots are automatically cleaned up (age + count limits).

```bash
peekxd cleanup --max-age 1 --max-files 50   # One-shot cleanup
```

### Robust Function Calling (v0.3.0)
The orchestrator uses structured Pydantic models + 4-strategy JSON parser instead of fragile regex extraction.

## Hermes Tool Reference

| Tool | What It Does |
|------|-------------|
| `peekxd_capture_screen` | Screenshot (screen/window/region) |
| `peekxd_analyze_screen` | Capture + AI analysis in one step |
| `peekxd_find_element` | Get x,y coordinates of any element by description |
| `peekxd_click` | Click at coordinates OR click element by description |
| `peekxd_type` | Type text |
| `peekxd_key` | Press key or hotkey combo |
| `peekxd_move_mouse` | Move cursor |
| `peekxd_scroll` | Scroll wheel |
| `peekxd_list_windows` | All windows with IDs |
| `peekxd_focus_window` | Focus by ID or title |
| `peekxd_inspect_ui` | Full UI element tree via AT-SPI2 |
| `peekxd_wait` | Wait for element/text/stable/change |
| `peekxd_run_sequence` | Execute multi-step action chain |
| `peekxd_mark_elements` | **Detect ALL elements with bounding boxes** |

## Python API for Agents

### Direct Tool Execution

```python
from peekxd.agent import execute_hermes_action, get_hermes_tool_definitions

# 1. Get tool schemas for your LLM
tools = get_hermes_tool_definitions()  # 14 Tools as JSON Schema

# 2. Execute any tool by name
result = execute_hermes_action("peekxd_mark_elements", {})
# -> {'elements': [...], 'markup_path': '/tmp/...png', 'count': 23}

# 3. Click with element description
result = execute_hermes_action("peekxd_click", {
    "element_description": "the red Submit button"
})
```

### Autonomous Task Execution

```python
from peekxd.agent import AgentOrchestrator

orch = AgentOrchestrator(
    max_steps=10,
    step_delay=1.0,
    safety_level=SafetyLevel.NORMAL,  # strict/normal/permissive
    enable_memory=True,               # Cache element positions
    enable_audit=True,                # Log all actions
)
result = orch.run_task("Open settings and enable dark mode")

print(f"Success: {result.success}")
print(f"Steps: {result.steps_taken}")
print(f"Summary: {result.summary}")
```

### Action Sequences

```python
from peekxd.agent import ActionSequence

seq = ActionSequence()
seq.find_click("Username field", retry=3)
seq.type("admin")
seq.key("Tab")
seq.type("password123")
seq.find_click("Login button")
seq.wait(2.0)
seq.capture()

results = seq.execute()
for r in results:
    print(f"{'OK' if r['success'] else 'FAIL'}: {r['description']}")
```

### Wait Conditions

```python
from peekxd.agent.actions import WaitCondition, ScreenDiff

# Wait for element
result = WaitCondition.for_element("Download complete", timeout=30)
# {'found': True, 'position': (400, 300), 'elapsed': 5.2}

# Wait for text
result = WaitCondition.for_text("Success!", timeout=10)

# Wait for screen to stabilize
result = WaitCondition.for_no_change(timeout=10)

# Detect screen changes
differ = ScreenDiff()
result = differ.wait_for_change(timeout=10)
```

### Screen Markup (Bounding Boxes)

```python
from peekxd.agent import analyze_screen_with_markup

result = analyze_screen_with_markup("/tmp/screenshot.png")
for elem in result["elements"]:
    print(f"[{elem['id']}] {elem['name']} at {elem['position']}")
# result["markup_path"] = image with numbered boxes drawn
```

### Session Memory

```python
from peekxd.agent.memory import AgentMemory

mem = AgentMemory()
mem.remember_element("Submit button", (500, 400), (80, 30))

# Later: cached position (no vision call needed)
pos = mem.recall_element("Submit button")
if pos:
    input.click(pos[0], pos[1])
```

### Safety Guard

```python
from peekxd.core.safety import SafetyGuard, SafetyLevel

guard = SafetyGuard(SafetyLevel.NORMAL)
try:
    guard.check_action("type", {"text": "rm -rf /home"})
except PermissionDeniedError as e:
    print(f"Blocked: {e}")

# Preview mode
result = guard.preview("click", {"x": 100, "y": 200})
# -> {'preview': True, 'action': 'click', ...}
```

## CLI Reference

### Agent Commands
```bash
peekxd agent run "TASK" [--max-steps N] [--step-delay S] [-v] [--safety strict|normal|permissive]
peekxd agent mark [--output PATH] [--prompt PROMPT]
peekxd agent tools                              # JSON tool definitions
```

### Safety Commands
```bash
peekxd safety check ACTION PARAMS_JSON           # Test if action passes safety
peekxd safety preview ACTION PARAMS_JSON         # Dry-run
```

### Macro / Sequence Commands
```bash
peekxd macro run '[{"action":"click","params":{"x":100,"y":200}}]'
```

### Wait Commands
```bash
peekxd wait-for --element "Submit button" [--timeout 10]
peekxd wait-for --text "Loading complete" [--timeout 30]
peekxd wait-for --stable [--timeout 10]
peekxd wait-for --change [--timeout 10]
```

### Audit Commands
```bash
peekxd audit show                 # Human-readable trail
peekxd audit export               # JSON export
peekxd audit summary              # Session statistics
```

### Cleanup
```bash
peekxd cleanup [--max-age HOURS] [--max-files N]
```

### Standard Commands
```bash
peekxd capture screen|window|region
peekxd click X Y [--button left|right|middle]
peekxd type TEXT
peekxd key KEY [--hotkey]
peekxd move X Y
peekxd scroll [--direction up|down|left|right]
peekxd window list|focus|move|resize
peekxd inspect tree|find
peekxd analyze IMAGE PROMPT
peekxd mcp [--transport stdio|sse]
peekxd permissions
```

## MCP Server (18 Tools)

```bash
peekxd mcp  # stdio mode for Claude Desktop, Cursor, etc.
```

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `PEEKXD_HERMES_AGENT_DIR` | Optional path to Hermes Agent checkout for the default Hermes vision provider |
| `HERMES_VISION_MODEL` | Optional Hermes auxiliary vision model override |
| `OPENAI_API_KEY` | Direct OpenAI Vision API fallback |
| `ANTHROPIC_API_KEY` | Direct Anthropic Claude Vision fallback |
| `OLLAMA_HOST` | Ollama server URL |

## Version

0.3.0 — Hermes Agent Edition with Safety, Memory, Audit, Cleanup
+
0.3.4 — Confirmable Ghost Actions (Softbox V4): Two-tier classification. APPROVABLE_GHOST reached via SHADOW zone routing (not GHOST zone). Approved safe SHADOW actions execute after overlay confirmation. Hard-blocked never do. New `--ghost-approval-execution` CLI flag.
0.3.3 — Softbox Ghost Live Overlay V3: live overlay for GHOST actions with approve/cancel/timeout
0.3.2 — Softbox Shadow Mode V2: before/after snapshots with shadow audit for normal actions
+0.3.1 — Softbox Ghost Mode: risk-based zone system with preview-only safety
