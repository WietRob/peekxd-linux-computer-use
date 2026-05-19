# Peekaboo v3 Parity Audit — Gap-Matrix + v0.4.0 Backport-Plan

**Date:** 2026-05-19
**Auditor:** Hermes Analyst (Kanban task t_cdd3e2d2)
**Peekaboo v3 Reference:** 3.2.1 (cloned from https://github.com/openclaw/Peekaboo)
**peekxd Reference:** main @ 9f6b52f (v0.3.4-confirmable-ghost-actions)

---

## 1. Executive Summary

Peekaboo v3 (3.2.1) is a mature macOS-native automation CLI + MCP server written in Swift. It has evolved into a comprehensive desktop-automation platform with snapshot-based element addressing, accessibility-first interaction, and a rich agent runtime. peekxd (v0.3.4) is a Linux-focused Python alternative that already covers the core vision + input primitives but lacks the structured snapshot/element-id semantics, AT-SPI2 accessibility depth, and several macOS-specific system integrations.

This audit identifies **37 capabilities**, classifies gaps, and proposes a **v0.4.0 roadmap** that adopts Peekaboo's *concepts* without copying its macOS implementation.

---

## 2. What Peekaboo v3 Is

- **Language / Platform:** Swift 6.2, macOS 15.0+ (Sequoia), arm64/Intel universal
- **Distribution:** Homebrew tap + npm package (`@steipete/peekaboo`) + signed .app
- **Architecture:** CLI (`Apps/CLI`) + Core library (`Core/PeekabooCore`) + Bridge/Daemon + MCP server + Agent runtime
- **Key Concepts:**
  - **Snapshot IDs:** Every `see` / `image` / `capture` generates a session-scoped snapshot with a unique ID. Subsequent element-targeted commands (`click --on`, `type --on`, `set-value`, `perform-action`) reference this snapshot for coordinate resolution and validation.
  - **Element IDs:** Within a snapshot, detected AX elements receive short IDs (e.g., `B1`, `T1`). Agents and scripts use these IDs instead of raw coordinates.
  - **Action-first automation:** Direct accessibility API calls (AXPress, AXSetValue, etc.) are preferred; synthetic mouse/keyboard input is fallback.
  - **Tachikoma:** Pluggable AI provider system (OpenAI, Anthropic, Gemini, Ollama, LM Studio, MiniMax, etc.).
  - **Daemon:** Warm background process for fast repeated screenshots and Bridge socket communication.
  - **MCP server:** Same tool semantics exposed via MCP (stdio/SSE/HTTP).
  - **Permissions doctor:** `peekaboo permissions status|grant` with TCC integration.
  - **Workflows / Reproducible sessions:** Config-driven, typed, testable.
  - **Cleanup:** `peekaboo clean --older-than 24` for snapshot cache management.

---

## 3. What peekxd Currently Is

- **Language / Platform:** Python 3.10+, Linux (X11 + experimental Wayland), WSLg support
- **Distribution:** pip install from GitHub (`git@github.com:WietRob/peekxd-linux-computer-use.git`)
- **Architecture:** Click-based CLI (`peekxd/`) + MCP server (`peekxd/mcp_server.py`) + Agent orchestrator + Vision provider (Hermes, OpenAI, Anthropic, Ollama)
- **Key Concepts:**
  - **Coordinate-based interaction:** `click X Y`, `move X Y`, `type TEXT` — no snapshot or element-id abstraction.
  - **Vision-based element finding:** `peekxd find_element "description"` uses AI vision to resolve coordinates on-the-fly.
  - **Agent mark mode:** `peekxd agent mark` captures screen, detects UI elements with AI, draws numbered bounding boxes.
  - **Safety / Ghost / Shadow / Overlay / Zones:** peekxd has advanced safety modes (Softbox family) that Peekaboo does not.
  - **Audit trail:** Session logging with export.
  - **Macro / Sequence runner:** JSON-driven multi-step action sequences (`peekxd macro run`).
  - **WSLg fallback:** Windows screenshot capture when running under WSL.

---

## 4. Feature-Matrix

| Capability | Peekaboo v3 | peekxd aktuell | Gap | Ubernehmen? | Prioritat | Kommentar |
|---|---|---|---|---|---|---|
| **screen capture** | Full (ScreenCaptureKit + CoreGraphics), `--retina`, `--mode screen` | Full (`capture screen`, `capture region`, `capture window`) | None | — | — | Both mature. peekxd has WSLg fallback. |
| **window capture** | Yes (`image --mode window`, `window_capture` tool) | Yes (`capture window`, `peekxd_capture_screen` with `mode=window`) | None | — | — | |
| **retina/scaling equivalent** | Yes (`--retina` 2x) | Partial (WSLg HiDPI aware, Linux scaling handled by backend) | Minor | Later | C | Linux scaling is display-server dependent. |
| **snapshot id** | Yes — central primitive. Every capture returns `snapshot_id`. | No — no snapshot concept. Each command is stateless. | **Major** | **Yes** | **A** | Core v0.4.0 primitive. Enables element-id addressing. |
| **element id** | Yes — short IDs (`B1`, `T1`) within snapshot. `click --on B1`, `type --on T1` | No — only coordinate-based or vision-description-based. | **Major** | **Yes** | **A** | Requires snapshot store + element detection cache. |
| **visual see** | Yes (`peekaboo see --json`) — captures + analyzes + returns snapshot + elements. | Yes (`peekxd see capture`) but no JSON element list or snapshot ID. | **Major** | **Yes** | **A** | `peekxd see --json` should return snapshot_id + element list. |
| **click by coordinates** | Yes (`click --coords X Y`) | Yes (`click X Y`) | None | — | — | |
| **click by element id/query** | Yes (`click --on B1 --snapshot SNAP`) | Partial (`find_element` then click, or `agent mark`) | **Major** | **Yes** | **A** | `peekxd click --on E1 --snapshot SNAP` needed. |
| **type text** | Yes (`type --text "hello"`, `type --on T1`) | Yes (`type TEXT`) | Minor | Yes | A | `type --on ELEMENT` requires snapshot. |
| **set accessibility value** | Yes (`set-value --on T1 --value "hello"`) | No | **Major** | Yes | B | Linux equivalent: AT-SPI2 `set_value`. |
| **perform accessibility action** | Yes (`perform-action --on B1 --action AXPress`) | No | **Major** | Yes | B | Linux equivalent: AT-SPI2 `do_action`. |
| **press key** | Yes (`press Return`, `press --count 3`) | Yes (`key KEY`) | None | — | — | |
| **hotkey** | Yes (`hotkey cmd+shift+4`) | Yes (`key --hotkey ['ctrl','c']`) | None | — | — | |
| **scroll** | Yes (`scroll --amount 5 --direction down`) | Yes (`scroll DIRECTION`) | None | — | — | |
| **drag/swipe** | Yes (`drag`, `swipe` with start/end coords or element IDs) | No | **Major** | Yes | B | `drag` and `swipe` CLI commands needed. |
| **move mouse** | Yes (`move --coords X Y` or `--on E1`) | Yes (`move X Y`) | Minor | Yes | B | `move --on ELEMENT` needs snapshot. |
| **window list/focus/move/resize** | Yes (`window list`, `window focus`, `window move`, `window resize`) | Yes (`window list`, `window focus`, `window move`, `window resize`) | None | — | — | |
| **app launch/quit/list** | Yes (`app launch`, `app quit`, `app list`, `app relaunch`) | No | **Major** | Yes | B | `peekxd app launch|quit|list` via `xdg-open` / `killall` / `ps`. |
| **menu list/click** | Yes (`menu list`, `menu click`, `menubar list`) | No | **Major** | Later | C | Linux has no unified global menu bar. App-specific menus via AT-SPI2 possible. |
| **menubar list/click** | Yes (`menubar list`, `menubar click`) | No | **Major** | Later | C | macOS-specific; no direct Linux equivalent. |
| **dock interaction** | Yes (`dock list`, `dock click`, `dock launch`) | No | **Major** | Later | C | Linux equivalent: panel/dock via D-Bus (GNOME Dash, KDE Panel). |
| **dialog interaction** | Yes (`dialog click`, `dialog input`, `dialog dismiss-list`) | No | **Major** | Later | C | Linux: AT-SPI2 dialog detection + interaction. |
| **space/workspace support** | Yes (`space list`, `space switch`, `space move-window`) | No | **Major** | Later | C | Linux: `wmctrl`/D-Bus workspace switching. |
| **image analyze** | Yes (`image --analyze`, `analyze` tool) | Yes (`analyze IMAGE PROMPT`) | None | — | — | |
| **agent natural-language loop** | Yes (`peekaboo agent "task"`) | Yes (`peekxd agent run "task"`) | Minor | Yes | B | Peekaboo has richer turn management + tool schema refresh. |
| **mcp server** | Yes (`peekaboo mcp serve --transport stdio|sse|http`) | Yes (`peekxd mcp --transport stdio|sse`) | Minor | Yes | A | Peekaboo has HTTP transport; peekxd only stdio/SSE. Also peekxd MCP tools lack snapshot semantics. |
| **config/providers** | Yes (`config init|show|edit|add-login|providers`) | Yes (`config` subcommand) | Minor | Yes | B | Peekaboo has `add-login` for keychain integration. |
| **permissions doctor** | Yes (`permissions status|grant`, TCC integration) | Yes (`permissions` — basic smoke check) | Minor | Yes | A | peekxd permissions doctor needs real capture smoke test. |
| **completions** | Yes (`completions generate` for bash/zsh/fish) | No | **Major** | Yes | B | Shell completion generation. |
| **workflow runner** | Yes (`run` command, reproducible sessions) | Partial (`macro run` for action sequences) | Minor | Yes | B | `peekxd workflow run` for named/config-driven workflows. |
| **cleanup snapshots** | Yes (`clean --all-snapshots|--older-than|--snapshot`) | Yes (`cleanup` command) | None | — | — | Both have cleanup. |
| **audit trail** | Yes (session history, `audit show|export|summary`) | Yes (`audit show|export|summary`) | None | — | — | |
| **safety zones** | No | Yes (`safety zones`, `zones` config) | **peekxd leads** | — | — | Peekaboo has no equivalent. |
| **before/after screenshots** | No | Yes (Ghost mode captures before/after) | **peekxd leads** | — | — | |
| **ghost overlay** | No | Yes (Softbox Ghost Live Overlay V3) | **peekxd leads** | — | — | |
| **confirmable ghost actions** | No | Yes (v0.3.4) | **peekxd leads** | — | — | |
| **Hermes vision provider** | No | Yes (v0.3.4+) | **peekxd leads** | — | — | |
| **WSLg support** | No | Yes | **peekxd leads** | — | — | |
| **Linux Wayland support** | No | Experimental | **peekxd leads** | — | — | Peekaboo is macOS-only. |
| **Linux X11 support** | No | Yes | **peekxd leads** | — | — | |
| **inspect_ui (AX-only)** | Yes (`inspect_ui` tool, `peekaboo agent` routes AX-only through it) | Partial (`inspect tree`, `inspect find`) | Minor | Yes | B | Peekaboo v3.2.1 added this recently. peekxd has basic AT-SPI2 tree. |
| **browser tool (MCP bridge)** | Yes (`browser` tool — page/navigate/click/fill/etc.) | No | **Major** | Later | C | Peekaboo has a full browser automation MCP bridge. |
| **background click (`--focus-background`)** | Yes (v3.2.0) | No | **Major** | Later | C | Click without stealing focus. Linux XTest may not support this cleanly. |
| **clipboard** | Yes (`clipboard copy|paste`, `copy_to_clipboard`, `paste_from_clipboard`) | No | Minor | Yes | B | `xclip`/`wl-copy` integration. |
| **paste command** | Yes (`paste --app Safari`) | No | Minor | Yes | B | Paste into specific app. |
| **daemon** | Yes (`daemon start|stop|status|run`) | No | **Major** | Later | C | Warm daemon for fast screenshots. peekxd could use a background Python daemon. |
| **capture engine selection** | Yes (`--capture-engine auto|cg|modern`) | No | Minor | Later | C | Linux has only one capture path per display server. |

---

## 5. Priorisierung

### A. Muss in peekxd v0.4.0

1. **`see` als zentrales Primitive mit Snapshot-ID**
   - `peekxd see --json` returns: `snapshot_id`, `elements[]` with `id`, `name`, `role`, `position`, `size`.
   - Snapshot stored in session cache (`~/.cache/peekxd/snapshots/`).

2. **Element-ID based click/type/inspect**
   - `peekxd click --on E1 --snapshot SNAP`
   - `peekxd type --on T1 --text "hello" --snapshot SNAP`
   - `peekxd inspect --snapshot SNAP`

3. **Snapshot store / session cache**
   - In-memory + disk cache with TTL.
   - `peekxd snapshot list`, `peekxd snapshot clean`.

4. **MCP/CLI gleiche Tool-Semantik**
   - MCP tools must accept `snapshot_id` and `element_id` parameters.
   - Proposed MCP tools: `peekxd_see`, `peekxd_click_on`, `peekxd_type_on`, `peekxd_inspect_snapshot`, `peekxd_snapshot_list`, `peekxd_snapshot_clean`.

5. **Permissions doctor mit echtem capture smoke**
   - `peekxd permissions` should attempt a real screenshot and report success/failure per subsystem.

6. **Docs: Peekaboo-v3-inspired parity target**
   - This audit document + ADR-0005.

### B. Sollte in v0.4.x

1. **set-value / perform-action via AT-SPI2**
   - `peekxd set-value --on E1 --value "hello"`
   - `peekxd perform-action --on B1 --action press`

2. **Window / app / menu primitives for Linux**
   - `peekxd app launch|quit|list`
   - `peekxd menu list|click` (app-specific via AT-SPI2)

3. **Workflow runner**
   - `peekxd workflow run workflow.yaml` — named, config-driven, reproducible.

4. **Completions**
   - `peekxd completions generate bash|zsh|fish`

5. **Agent enhancements**
   - Tool schema refresh per turn (like Peekaboo v3.2.1).
   - `inspect_ui` as AX-only fallback (no screenshot).

### C. Spater

1. **Dock / panel / space / dialog analogien**
   - Linux-specific implementations via D-Bus / `wmctrl` / AT-SPI2.

2. **Benchmark suite**
   - Capture latency, click accuracy, agent task success rate.

3. **Background execution without cursor stealing**
   - Linux XTest limitation research; possible via `xdotool` with `--window`.

4. **Wayland hardening**
   - Better portal integration, session restoration.

5. **Daemon**
   - Background Python process for warm screenshots and state caching.

6. **Browser tool**
   - Playwright/Selenium MCP bridge (large scope).

---

## 6. Was Bewusst NICHT Ubernommen Wird

| Peekaboo v3 Feature | Grund |
|---|---|
| macOS-specific TCC / Accessibility permissions model | Linux uses polkit, D-Bus, AT-SPI2 registry. Different permission architecture. |
| CoreGraphics / ScreenCaptureKit capture engines | Linux uses `mss`, `PIL`, `grim`, `scrot`, or display-server specific APIs. |
| macOS Dock / Spaces / Menu Bar | Linux has no unified global menu bar or Dock API. Panel implementations vary (GNOME, KDE, XFCE). |
| Swift / Xcode build system | peekxd is Python; no Swift toolchain dependency. |
| Signed .app bundle / Sparkle / Notarization | Linux distribution is pip/source; no Apple ecosystem. |
| `AXPress`, `AXIncrement` action names | Linux AT-SPI2 uses different action names (`click`, `press`, `activate`). Semantic mapping needed, not direct copy. |

---

## 7. Evidence

### peekxd Git State
- Branch: `main`, up to date with `origin/main`
- Latest commit: `9f6b52f fix: add WSLg Windows screenshot fallback`
- Tags: `v0.3.2-shadow-v2`, `v0.3.3-ghost-live-overlay`, `v0.3.3-ghost-live-overlay-reviewed`, `v0.3.3-publication-hygiene`, `v0.3.4-confirmable-ghost-actions`
- Remote: `git@github.com:WietRob/peekxd-linux-computer-use.git`
- No VERSION file (version inferred from tags / `peekxd/__init__.py`)

### peekxd Test Results
- `python3 -m pytest tests/ -q`: **451 passed, 4 failed, 2 skipped**
- 4 failures: `ModuleNotFoundError: No module named 'PIL'` (Pillow missing — dependency issue, not code issue)
- 8 collection errors initially: `NameError: name 'Field' is not defined` (missing `pydantic`) — resolved after `pip3 install pydantic`

### Peekaboo v3 Git State
- Cloned from: `https://github.com/openclaw/Peekaboo`
- Version: `3.2.1` (from `version.json` and `package.json`)
- Latest commit: `96a165d chore(release): close 3.2.1`
- Language: Swift 6.2, Node 22+ (MCP wrapper)
- Platform: macOS 15.0+ (Sequoia)

---

## 8. Top-5 Gaps

1. **Snapshot / Element-ID semantics** — peekxd is stateless per command; Peekaboo's snapshot is the core architectural primitive.
2. **Accessibility-first interaction (`set-value`, `perform-action`)** — peekxd only does synthetic input; no AT-SPI2 value setting or action invocation.
3. **App / Menu / Dock / Dialog / Space system integration** — peekxd has none of these; Peekaboo has rich macOS system integration.
4. **MCP tool richness** — Peekaboo exposes ~40 tools; peekxd exposes ~15. Missing: `app_*`, `menu_*`, `dock_*`, `dialog_*`, `space_*`, `clipboard`, `browser`.
5. **Completions + Workflow runner** — Peekaboo has shell completions and reproducible workflows; peekxd has only basic macros.

---

## 9. Risks

| Risk | Mitigation |
|---|---|
| AT-SPI2 APIs vary between GNOME/KDE/XFCE | Test on major DEs; document limitations. |
| Snapshot cache could grow unbounded | Implement TTL + size limits; `snapshot clean` command. |
| Element IDs from AI vision are non-deterministic | Use stable heuristics (position + role + label hash); fallback to re-detection. |
| Wayland limitations (no global coordinates) | Document Wayland caveats; prioritize X11 + WSLg. |
| Scope creep into full Peekaboo clone | Strict ADR boundary: adopt *concepts*, not *implementation*. |

---

*End of Gap-Matrix Audit*
