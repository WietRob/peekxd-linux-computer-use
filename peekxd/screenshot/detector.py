"""Screenshot provider selection for peekxd.

Visible screenshot capture has been intentionally removed from the default
PeekXD runtime because GNOME/Wayland/x-d-g-desktop-portal prompts can disturb
or block the user's live desktop. PeekXD's supported observation primitive is
now semantic accessibility/window state (``peekxd see --semantic``), not pixels.
"""

from ..core.errors import ProviderNotAvailableError
from .base import ScreenshotProvider

REMOVED_SCREENSHOT_MESSAGE = (
    "Visible screenshot capture is removed from PeekXD's default runtime. "
    "Use `peekxd see --semantic` for non-disturbing accessibility/window state."
)


def get_screenshot_provider() -> ScreenshotProvider:
    """Screenshots are intentionally unavailable.

    This function exists only as a compatibility seam for old callers. It never
    selects portal, gnome-screenshot, grim, wayshot, Spectacle, Flameshot, X11,
    WSL host capture, or PipeWire providers.
    """
    raise ProviderNotAvailableError(REMOVED_SCREENSHOT_MESSAGE)
