"""Auto-detect and return the best window provider for the current session."""

from peekxd.core.desktop import DesktopEnvironment, detect_desktop
from peekxd.core.errors import ProviderNotAvailableError
from peekxd.window.base import WindowProvider
from peekxd.window.x11 import X11WindowProvider
from peekxd.window.wayland import WaylandWindowProvider


def get_window_provider() -> WindowProvider:
    """Detect the desktop environment and return a suitable window provider.

    The provider is chosen in this order:

    1. Detect whether X11 or Wayland is running.
    2. Try the native provider for that platform first.
    3. Fall back to the cross-platform alternative.
    4. Raise ``ProviderNotAvailableError`` if nothing works.

    Returns:
        An instance of a ``WindowProvider`` subclass.

    Raises:
        ProviderNotAvailableError: If no window provider tools are installed.
    """
    desktop = detect_desktop()

    if desktop == DesktopEnvironment.X11:
        providers = [X11WindowProvider(), WaylandWindowProvider()]
    elif desktop == DesktopEnvironment.WAYLAND:
        providers = [WaylandWindowProvider(), X11WindowProvider()]
    else:
        # Unknown desktop - try X11 first (more common), then Wayland
        providers = [X11WindowProvider(), WaylandWindowProvider()]

    for provider in providers:
        if provider.available:
            return provider

    raise ProviderNotAvailableError(
        "No window provider available. Install: xdotool (X11) or wlrctl/swaymsg (Wayland)."
    )
