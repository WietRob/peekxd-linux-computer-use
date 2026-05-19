# Troubleshooting peekxd for Linux

## Installation Issues

### "No module named peekxd"
```bash
# Ensure package is installed
pip install -e ".[all]"

# Ensure PATH includes user bin
export PATH="$HOME/.local/bin:$PATH"
```

### System dependencies missing

**Ubuntu/Debian:**
```bash
sudo apt-get install xdotool imagemagick grim ydotool python3-pyatspi2
```

**Fedora:**
```bash
sudo dnf install xdotool ImageMagick grim ydotool pyatspi2
```

**Arch:**
```bash
sudo pacman -S xdotool imagemagick grim ydotool python-atspi
```

---

## Screenshot Issues

### "No screenshot provider available"

Install at least one of:
- **X11**: `imagemagick` (provides `import` command)
- **Wayland**: `grim`
- **WSLg**: `powershell.exe` and `wslpath` available from WSL (auto-detected)
- **Generic**: `spectacle`, `flameshot`, or `gnome-screenshot`

Verify:
```bash
which import    # X11
which grim      # Wayland
which powershell.exe wslpath  # WSLg fallback
which spectacle # Generic
```

### WSLg root capture fails with BadMatch / Resource temporarily unavailable

WSLg can expose both `DISPLAY` and `WAYLAND_DISPLAY`, while X11 root capture
via ImageMagick `import -window root` or `xwd -root` fails at runtime with:

```text
BadMatch (invalid parameter attributes)
unable to read X window image `root': Resource temporarily unavailable
```

peekxd includes a WSLg fallback provider that captures the actual Windows host
desktop through PowerShell/.NET (`System.Drawing.CopyFromScreen`). Verify it
with:

```bash
peekxd permissions
peekxd capture screen -o /tmp/peekxd-wslg.png
```

Expected permissions output in WSLg is `Screenshot: OK` even if native Wayland
tools such as `grim` are not installed.

### Black screenshots

Usually means the tool lacks permissions:
- **X11**: Should work out of the box
- **Wayland**: Some compositors require explicit permission. Check compositor docs.
- **spectacle**: May need "Screen Recording" permission in KDE System Settings

### Window capture not working

Window capture requires additional tools:
- **X11**: `xdotool` (for window ID lookup)
- **Wayland**: `swaymsg` or `wlrctl` (for window geometry)

---

## Input Issues

### "No input provider available"

Install:
- **X11**: `xdotool`
- **Wayland**: `ydotool` + `ydotoold` daemon

### ydotool "cannot connect to socket"

The ydotoold daemon must be running:
```bash
# Check if running
ps aux | grep ydotoold

# Start manually
ydotoold &

# Or via systemd (installed by install.sh)
systemctl --user start ydotoold

# If socket permission denied:
sudo chmod 666 /run/ydotoold/socket
```

### xdotool "command not found"

```bash
sudo apt-get install xdotool  # Debian/Ubuntu
sudo dnf install xdotool      # Fedora
sudo pacman -S xdotool        # Arch
```

### Typing special characters fails

xdotool has limited Unicode support. For complex text:
- Use copy-paste via clipboard instead
- Or install `xvkbd` as alternative

---

## Inspection Issues

### "No inspection provider available"

Install `python3-pyatspi2`:
```bash
sudo apt-get install python3-pyatspi2 at-spi2-core
```

### AT-SPI2 returns empty tree

AT-SPI2 requires:
1. A running desktop session (not headless)
2. The AT-SPI registry daemon:
   ```bash
   ps aux | grep at-spi
   # If not running:
   /usr/libexec/at-spi2-registryd &
   ```
3. Applications must expose accessibility info. Some apps (browsers, electron) need explicit enabling.

### Headless/server environments

AT-SPI2 does not work without a display. For servers:
- Use screenshots + vision analysis instead
- Or run a virtual display (Xvfb) for X11 apps

---

## Window Management Issues

### "No window provider available"

Install:
- **X11**: `xdotool`
- **Wayland**: `wlrctl` (for wlroots compositors) or `swaymsg` (for Sway)

**Note:** Generic Wayland compositors (non-wlroots) may not support window management at all.

### Window focus not working on Wayland

Wayland has stricter security. Some compositors:
- **Sway**: Works with `swaymsg`
- **Hyprland**: Use `hyprctl` (not yet supported — use wlrctl)
- **GNOME**: Limited scripting via `gdbus`
- **KDE**: Use `qdbus` with KWin scripts

### "Cannot resize window"

Some tiling window managers ignore resize requests. Use the WM's native commands instead.

---

## Vision Issues

### "No vision provider available"

Prefer Hermes Agent when available; peekxd then reuses Hermes' configured auxiliary vision backend and does not need its own API key:
```bash
# Optional if Hermes is not in the default location:
export PEEKXD_HERMES_AGENT_DIR="$HOME/.hermes/hermes-agent"
peekxd permissions
```

Fallback options are direct provider credentials or local Ollama:
```bash
export OPENAI_API_KEY="sk-..."
# or
export ANTHROPIC_API_KEY="sk-ant-..."
# or start Ollama
ollama run llava:latest
```

### OpenAI "invalid API key"

- Check key format: should start with `sk-`
- Verify key at: https://platform.openai.com/api-keys

### Ollama "connection refused"

```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Start Ollama
ollama serve &

# Pull a vision model
ollama pull llava:latest
```

### "fastmcp not installed" for MCP

```bash
pip install fastmcp
# or
pip install -e ".[mcp]"
```

---

## Desktop Environment Matrix

| Environment | Screenshot | Input | Window | Inspection | Notes |
|-------------|-----------|-------|--------|------------|-------|
| KDE X11 | Full | Full | Full | Partial | AT-SPI2 works, some KDE apps need export |
| KDE Wayland | Full | Partial | Partial | Partial | ydotool+grim needed |
| GNOME X11 | Full | Full | Full | Full | Best supported |
| GNOME Wayland | Full | Partial | Limited | Partial | Use gdbus for windows |
| Sway | Full | Full* | Full | Partial | *ydotoold needed |
| Hyprland | Full | Full* | Partial | Partial | *ydotoold needed |
| i3wm | Full | Full | Full | Full | X11 — full support |
| XFCE | Full | Full | Full | Full | X11 — full support |

---

## Getting Help

1. Run self-test: `./selftest.sh`
2. Check permissions: `peekxd permissions`
3. Run with verbose: `peekxd -v ...`
4. Check logs in `~/.cache/peekxd/`
5. File issue: https://github.com/peekxd-linux/peekxd/issues
