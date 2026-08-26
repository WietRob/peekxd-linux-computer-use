"""Screenshot module compatibility surface.

Real screenshot capture (G3 correction): provider selection and pixel capture
are fully re-enabled. ``peekxd capture screen|window|region`` performs real
captures through the detected provider and reports sha256 + path.
"""

from .base import ScreenshotProvider
from .detector import (
    REMOVED_SCREENSHOT_MESSAGE,
    get_screenshot_provider,
)
from .generic import GenericProvider
from .pipewire import PipeWireScreenCastProvider
from .portal import XdgDesktopPortalProvider
from .wayland import WaylandProvider
from .windows_wsl import WindowsWslProvider, WSLgScreenshotProvider
from .x11 import X11Provider

__all__ = [
    "ScreenshotProvider",
    "REMOVED_SCREENSHOT_MESSAGE",
    "get_screenshot_provider",
    "GenericProvider",
    "PipeWireScreenCastProvider",
    "XdgDesktopPortalProvider",
    "WaylandProvider",
    "WindowsWslProvider",
    "WSLgScreenshotProvider",
    "X11Provider",
]
