# PeekXD PipeWire-first Out-of-Box Hermes Roadmap (Linux)

Goal: land a user-safe, repeatable first-run path for peekxd on Linux/Wayland where
PipeWire ScreenCast is the preferred silent-ish route and xdg-desktop-portal screenshot is used as a consent-aware fallback, with no repeated visible capture flashes during diagnostics.

Scope context
- Parent ops task completed: `t_c5e8de86` implemented PipeWire/portal code and mock tests.
- Parent design task: `t_1ce062f8`.
- This roadmap is for productionizing that change for first-run in Hermes profiles.

Current evidence snapshot (already verified in this workspace)
- `git status --short` shows code changes in:
  - `peekxd/core/doctor.py`
  - `peekxd/screenshot/__init__.py`
  - `peekxd/screenshot/detector.py`
  - `tests/test_doctor.py`
  - `tests/test_screenshot.py`
  - `peekxd/screenshot/portal.py`
  - `peekxd/screenshot/pipewire.py`
- `python3 -m py_compile ...` passes on modified files.
- `python3 -m pytest tests/test_doctor.py tests/test_screenshot.py -q` returned `63 passed`.
- `peekxd doctor --capability screenshot --smoke` on this Wayland host returns:
  `WARN via XdgDesktopPortalProvider — Screenshot provider detected, but smoke capture is skipped because this path is user-consent driven.`
- `peekxd doctor --json` reports provider chain and shows screenshot provider as `XdgDesktopPortalProvider` with `smoke_tested: false` (expected with no visible-flash mode).

---

Prioritized roadmap

## P0 (must happen before broader rollout)

1) Package/OS bootstrap path with distro detection
- Add a single bootstrap command (or documented one-liner set) for required packages:

```bash
if command -v apt-get >/dev/null 2>&1; then
  sudo apt-get update
  sudo apt-get install -y \
    xdotool imagemagick python3-gi python3-dbus \
    libglib2.0-bin xdg-desktop-portal xdg-desktop-portal-gnome \
    gir1.2-atspi-2.0  # optional for full inspection on Debian/Ubuntu
elif command -v dnf >/dev/null 2>&1; then
  sudo dnf install -y \
    xdotool ImageMagick python3-gobject-base dbus-python glib2
elif command -v pacman >/dev/null 2>&1; then
  sudo pacman -Syu --noconfirm \
    xdotool imagemagick gobject-introspection python-gobject python-dbus
else
  echo "No supported pkg manager found (apt/dnf/pacman)."
  exit 1
fi
```

Notes:
- Include `grim`/`wayshot` only if native Wayland paths are expected; keep portal-first to reduce dead-end X11/wayland assumptions.
- `libglib2.0-bin`/`gdbus` is important because both portal and smoke diagnostics rely on `gdbus` introspection.

2) Create one-shot explicit consent install guide for first user-visible capture
- Keep all health checks non-interactive by default.
- Add/keep explicit operator step for any consent-driven screenshot path:

```bash
# non-invasive capability checks only
peekxd doctor
peekxd doctor --json
peekxd doctor --smoke
peekxd doctor --capability screenshot --smoke

# one explicit visible capture when needed
peekxd capture screen -o /tmp/peekxd-onboard-smoke.png
```

Do not run screenshot portal in loops or repeated polling.

3) Profile-aware Hermes MCP activation gate
For each active profile (`pm`, `ops`, `analyst`, `reviewer`) run:

```bash
hermes -p <profile> mcp list
hermes -p <profile> mcp test peekxd
hermes -p <profile> mcp configure peekxd   # if tool filtering needed
hermes -p <profile> tools list | grep -i peekxd
```

Then run a new shell/session start for the target profile so tool discovery is loaded at startup.

4) Add user-visible launch checklist (no repeated flash)
Use exactly this order in onboarding docs:

1. `peekxd --help`
2. `peekxd doctor`
3. `peekxd doctor --json`
4. `peekxd doctor --smoke`
5. `peekxd compatibility --json`
6. `peekxd window list`
7. `peekxd inspect tree`
8. `hermes -p <profile> mcp list`
9. `hermes -p <profile> mcp test peekxd`
10. Optional one-off consent capture: `peekxd capture screen -o ...`

If any step flips from WARN to FAILED, stop and report block reason before proceeding.

## P1 (important once P0 is stable)

1) Complete PipeWire integration hardening (skeleton -> session flow)
- current `PipeWireScreenCastProvider` is intentionally conservative and explicit-session-only.
- next work items:
  - define and persist a real screencast session lifecycle (start/stop tokens)
  - cache session readiness in a secure location
  - implement `list_screens()`/selection once screen enumeration exists in chosen compositor path
  - keep `supports_background_capture=False` unless portal session is explicit and still bounded.

2) Package docs alignment
- Align README prerequisites with actual provider matrix:
  - Wayland screenshot: `grim`/`wayshot` (best-effort) + portal flow
  - GNOME/portal path needs `python3-dbus` + `python3-gi`
  - PipeWire session still explicit-consent and not background-capture-safe by default

3) Expand smoke assertions into a no-flicker CI gate
- Add one dedicated, profile-agnostic scripted check that only inspects `screenshot` status + `provider` + warning text.
- Fail if `peekxd doctor --capability screenshot --smoke` enters an actual capture flow on non-interactive mode.

## P2 (after acceptance)

1) Add runtime UX for per-session consent state
- Add an explicit `peekxd screenshot consent status` command or config flag to show:
  - portal-screencast session discovered
  - explicit session marker presence (`PEEKXD_PIPEWIRE_SCREENCAST_SESSION`)
  - last consent timestamp

2) Installer wrapper (optional)
- Add optional `install-deps` helper script (non-destructive, read-only detection + package hints) that:
  - detects distro family
  - prints exact apt/dnf/pacman commands
  - does not perform installs without explicit confirmation

3) Acceptance and rollout metric
- Release criteria:
  - provider detection deterministic and fast
  - no background automatic screenshot in portal/pipewire paths
  - reviewer and PM confirm no repeat portal flash behavior in diagnostic lanes

Operational guardrails
- Use `visible_capture_required` evidence in doctor as a hard policy gate.
- Treat repeated portal prompt complaint as a blocker for rollout until operator accepts one-shot behavior.
- Any code that calls capture in background smoke must either skip or prove explicit consent.

Acceptance for this roadmap
- [ ] P0 items implemented and documented
- [ ] One successful profile smoke run with `hermes -p <profile> mcp test peekxd`
- [ ] `peekxd doctor --capability screenshot --smoke` remains WARN and non-capturing in non-interactive mode
- [ ] One explicit consent capture can be executed with one command by human operator
- [ ] No portal capture loops in logs/docs/telemetry during onboarding

