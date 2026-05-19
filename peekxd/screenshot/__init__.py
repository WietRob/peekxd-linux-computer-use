"""Screenshot module for peekxd Linux.

Provides platform-aware screenshot capture for X11, Wayland, and generic
 desktop environments with automatic provider selection.
"""

from .base import ScreenshotProvider
from .detector import get_screenshot_provider
from .generic import GenericProvider
from .wayland import WaylandProvider
from .windows_wsl import WindowsWslProvider
from .x11 import X11Provider

__all__ = [
    "ScreenshotProvider",
    "X11Provider",
    "WaylandProvider",
    "WindowsWslProvider",
    "GenericProvider",
    "get_screenshot_provider",
]
