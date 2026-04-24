"""Auto-detect the best input provider for the current session."""

from peekxd.core.desktop import detect_desktop, DesktopEnvironment
from peekxd.core.errors import ProviderNotAvailableError
from peekxd.input.base import InputProvider
from peekxd.input.x11 import X11InputProvider
from peekxd.input.wayland import WaylandInputProvider


def get_input_provider() -> InputProvider:
    """Auto-detect and return the best input provider.

    The detection strategy is:

    1. Detect the current desktop environment (X11 or Wayland).
    2. For X11, prefer X11InputProvider, fallback to WaylandInputProvider.
    3. For Wayland, prefer WaylandInputProvider, fallback to X11InputProvider.
    4. If the desktop environment is unknown, try X11 first, then Wayland.
    5. Raise ProviderNotAvailableError if none are available.

    Returns:
        An InputProvider instance ready for use.

    Raises:
        ProviderNotAvailableError: No suitable input provider is available.
    """
    desktop = detect_desktop()

    if desktop == DesktopEnvironment.X11:
        providers = [X11InputProvider(), WaylandInputProvider()]
    elif desktop == DesktopEnvironment.WAYLAND:
        providers = [WaylandInputProvider(), X11InputProvider()]
    else:
        # Unknown desktop — try X11 first as the most common fallback
        providers = [X11InputProvider(), WaylandInputProvider()]

    for provider in providers:
        if provider.available:
            return provider

    raise ProviderNotAvailableError(
        "No input provider available. Install: xdotool (X11) or ydotool (Wayland)."
    )
