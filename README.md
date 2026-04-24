# peekxd — Linux Computer Use

> Linux automation that sees the screen and does the clicks.
> Inspired by peekxd (Peter Steinberger) — ported from macOS to Linux.

peekxd gives AI agents eyes and hands on Linux. Capture screenshots, analyze them with AI vision models, control the mouse and keyboard, inspect UI elements, manage windows — all through a clean CLI or MCP server.

## Features

| Feature | Status | Description |
|---------|--------|-------------|
| Screenshot | Ready | Full screen, window, region capture (X11 + Wayland) |
| Input | Ready | Mouse move, click, type, hotkey, scroll, drag |
| Inspection | Ready | UI element tree via AT-SPI2 |
| Window | Ready | List, focus, move, resize, close windows |
| Vision | Ready | OpenAI, Anthropic, Ollama providers |
| MCP Server | Ready | 18 tools for AI assistants |
| CLI | Ready | Full command-line interface |
| **Agent Markup** | **v0.3.0** | AI-powered bounding box detection |
| **Autonomous Loop** | **v0.3.0** | See-Think-Act with configurable steps |
| **Softbox Shadow** | **v0.3.2** | Before/After Snapshots + Shadow Audit for normal actions |
| **Softbox Ghost Live Overlay** | **v0.3.3** | Live overlay for GHOST actions with approve/cancel/timeout |
| **Safety Guardrails** | **v0.3.0** | Strict/Normal/Permissive safety levels |
| **Session Memory** | **v0.3.0** | Cached element positions across tasks |
| **Audit Trail** | **v0.3.0** | Per-action logging with JSON export |
| **Auto-Cleanup** | **v0.3.0** | Scheduled temp file cleanup |

## Architecture

```
peekxd/
├── core/           # Desktop detection, errors, utilities, safety, cleanup, audit
├── screenshot/     # X11, Wayland, Generic providers
├── input/          # xdotool (X11), ydotool (Wayland)
├── inspection/     # AT-SPI2 accessibility
├── window/         # xdotool/wlrctl window management
├── vision/         # OpenAI, Anthropic, Ollama
├── agent/          # Orchestrator, actions, markup, memory, function calling, Hermes tools
├── mcp_server/     # FastMCP server (18 tools)
├── config/         # JSON configuration
└── cli.py          # Click CLI
```

## Installation

### Prerequisites

**Required:**
- Python 3.10+
- For X11: `xdotool`, `imagemagick`
- For Wayland: `grim`, `ydotool`

**Optional:**
- `spectacle` or `flameshot` (alternative screenshot)
- `wlrctl` (Wayland window management)
- `python3-pyatspi2` (UI inspection)
- `pydantic` (structured function calling)

### Quick Install

```bash
# 1. Clone
git clone https://github.com/peekxd-linux/peekxd.git
cd peekxd

# 2. Install system dependencies (Ubuntu/Debian)
sudo apt-get install -y xdotool imagemagick grim ydotool python3-pyatspi2

# 3. Install Python package
pip install -e ".[all]"

# 4. Verify
peekxd permissions
```

## Quick Start

```bash
# Capture full screen
peekxd capture screen -o screenshot.png

# Capture specific window
peekxd capture window --id 12345678

# Capture region (x y width height)
peekxd capture region 100 100 500 300

# Click at coordinates
peekxd click 500 400

# Type text
peekxd type "Hello, World!"

# Press hotkey
peekxd key ctrl,c --hotkey

# List windows
peekxd window list

# Focus window
peekxd window focus 12345678

# Get UI tree
peekxd inspect tree --app firefox

# Analyze with AI (requires API key)
peekxd analyze screenshot.png "What do you see?"

# Mark all elements with bounding boxes
peekxd agent mark

# Run autonomous task
peekxd agent run "Open Firefox and go to github.com"

# Run MCP server
peekxd mcp
```

## Configuration

```bash
# Create default config
peekxd config init

# Show config
peekxd config show

# Set value
peekxd config set vision.default_provider ollama
peekxd config set vision.ollama_model llava:latest

# Get value
peekxd config get vision.default_provider
```

Config location: `~/.config/peekxd/config.json`

### Vision Providers

**OpenAI:**
```bash
export OPENAI_API_KEY="sk-..."
peekxd config set vision.default_provider openai
```

**Anthropic:**
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
peekxd config set vision.default_provider anthropic
```

**Ollama (local):**
```bash
ollama run llava:latest
peekxd config set vision.default_provider ollama
peekxd config set vision.ollama_host http://localhost:11434
```

## MCP Server

peekxd runs as an MCP server for integration with AI assistants:

```bash
# stdio transport (default)
peekxd mcp

# SSE transport
peekxd mcp --transport sse --port 3000
```

### Available MCP Tools

| Tool | Description |
|------|-------------|
| `capture_screen` | Capture screen/window/active |
| `move_mouse` | Move mouse to coordinates |
| `click` | Click at coordinates |
| `type_text` | Type text |
| `press_key` | Press a key |
| `list_windows` | List all windows |
| `focus_window` | Focus a window |
| `get_ui_tree` | Get UI element tree |
| `find_element` | Find UI element by name/role |
| `analyze_image` | Analyze image with AI |
| `get_active_window` | Get focused window |
| `mark_elements` | **Detect all UI elements with bounding boxes** |
| `find_and_click` | Find element + click in one step |
| `type_into_field` | Find field + type in one step |
| `wait_for_element` | Wait until element appears |
| `wait_for_text` | Wait until text is visible |
| `run_action_sequence` | Execute multi-step chains |
| `screen_has_changed` | Detect if screen changed |

## Safety Features

peekxd includes configurable safety guardrails:

```bash
# Strict mode — preview only, no execution
peekxd agent run "TASK" --safety strict

# Normal mode — blocks destructive commands (default)
peekxd agent run "TASK" --safety normal

# Permissive mode — minimal checks
peekxd agent run "TASK" --safety permissive

# Test if an action would be blocked
peekxd safety check type '{"text": "rm -rf /"}'

# Dry-run
peekxd safety preview click '{"x": 100, "y": 200}'
```

## Agent Autonomous Mode

```bash
# Run a task autonomously
peekxd agent run "Open the settings app and enable dark mode"

# With more steps and verbose output
peekxd agent run "Install VS Code" --max-steps 20 -v

# With strict safety
peekxd agent run "Clean up Downloads folder" --safety strict
```

## Desktop Support

| Feature | X11 | Wayland | Notes |
|---------|-----|---------|-------|
| Screenshot | Full | Full | grim (Wayland), import (X11) |
| Input | Full | Full | ydotool needs daemon |
| Window | Full | Partial | wlrctl only for wlroots |
| Inspection | Full | Partial | AT-SPI2 availability varies |
| Vision | Full | Full | No DE dependency |

### Tested On

- KDE Plasma 6 (X11 & Wayland)
- GNOME 45+ (Wayland)
- Sway (Wayland)
- Hyprland (Wayland)
- i3wm (X11)

## CLI Reference

```
peekxd [OPTIONS] COMMAND [ARGS]...

Commands:
  capture     Capture screenshots
  click       Click at X Y
  type        Type TEXT
  key         Press KEY
  move        Move mouse to X Y
  scroll      Scroll in DIRECTION
  window      Window management
  inspect     UI inspection
  analyze     Analyze image with AI
  agent       AI agent automation
  macro       Action sequences
  wait-for    Wait for condition
  safety      Safety guardrails
  audit       Audit trail
  cleanup     Clean up temp files
  config      Configuration
  permissions Check permissions
  mcp         Run MCP server
  version     Show version
```

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run specific module tests
pytest tests/test_safety.py -v
pytest tests/test_memory.py -v
pytest tests/test_cleanup.py -v
pytest tests/test_audit.py -v

# Self-test
./selftest.sh
```

## Troubleshooting

See TROUBLESHOOTING.md in this directory.

## License

MIT

## Version

0.3.3 — Softbox Ghost Live Overlay V3: live overlay for GHOST actions with approve/cancel/timeout
0.3.2 — Softbox Shadow Mode V2: before/after snapshots with shadow audit for normal actions
0.3.1 — Softbox Ghost Mode: risk-based zone system with preview-only safety
