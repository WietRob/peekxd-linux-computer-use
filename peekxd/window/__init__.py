"""Window management module for peekxd Linux.

Provides cross-desktop window operations via X11 (xdotool) and
Wayland (wlrctl / swaymsg) backends.
"""

from peekxd.window.base import WindowProvider
from peekxd.window.x11 import X11WindowProvider
from peekxd.window.wayland import WaylandWindowProvider
from peekxd.window.detector import get_window_provider

__all__ = [
    "WindowProvider",
    "X11WindowProvider",
    "WaylandWindowProvider",
    "get_window_provider",
]
