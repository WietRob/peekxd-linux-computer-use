"""Desktop environment detection for Linux."""

import enum
import os


class DesktopEnvironment(enum.Enum):
    """Supported desktop environment types."""

    X11 = "x11"
    WAYLAND = "wayland"
    UNKNOWN = "unknown"


def detect_desktop() -> DesktopEnvironment:
    """Detect whether we're running on X11 or Wayland.

    Checks in order:
    1. WAYLAND_DISPLAY env var
    2. XDG_SESSION_TYPE env var
    3. DISPLAY env var (fallback to X11)
    """
    wayland_display = os.environ.get("WAYLAND_DISPLAY", "")
    if wayland_display:
        return DesktopEnvironment.WAYLAND

    session_type = os.environ.get("XDG_SESSION_TYPE", "").lower()
    if session_type == "wayland":
        return DesktopEnvironment.WAYLAND
    if session_type == "x11":
        return DesktopEnvironment.X11

    display = os.environ.get("DISPLAY", "")
    if display:
        return DesktopEnvironment.X11

    return DesktopEnvironment.UNKNOWN


def is_x11() -> bool:
    """Check if running on X11."""
    return detect_desktop() == DesktopEnvironment.X11


def is_wayland() -> bool:
    """Check if running on Wayland."""
    return detect_desktop() == DesktopEnvironment.WAYLAND
