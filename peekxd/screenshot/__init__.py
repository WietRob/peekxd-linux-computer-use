"""Screenshot module compatibility surface.

Visible screenshot capture has been removed from PeekXD. Provider classes remain
importable only as stubs so old imports fail closed instead of triggering pixel
capture or desktop portal prompts.
"""

from .base import ScreenshotProvider
from .detector import REMOVED_SCREENSHOT_MESSAGE, get_screenshot_provider
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
