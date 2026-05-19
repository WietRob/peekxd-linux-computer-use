"""Auto-detect the best screenshot provider for the current environment."""

from ..core.desktop import DesktopEnvironment, detect_desktop
from ..core.errors import ProviderNotAvailableError
from .base import ScreenshotProvider
from .generic import GenericProvider
from .wayland import WaylandProvider
from .windows_wsl import WindowsWslProvider
from .x11 import X11Provider


def get_screenshot_provider() -> ScreenshotProvider:
    """Auto-detect and return the best screenshot provider.

    The detection order depends on the detected desktop environment:

    - **WSL/WSLg**: WindowsWslProvider -> native desktop providers -> GenericProvider
    - **X11**: X11Provider -> GenericProvider
    - **Wayland**: WaylandProvider -> GenericProvider
    - **Unknown**: X11Provider -> WaylandProvider -> GenericProvider

    Returns:
        An instance of the first available :class:`ScreenshotProvider`.

    Raises:
        ProviderNotAvailableError: If no provider is available.
    """
    desktop = detect_desktop()
    wsl_provider = WindowsWslProvider()

    if wsl_provider.available:
        # WSLg often advertises Wayland/X11 while root capture fails at runtime
        # (BadMatch / unable to read X window image root). Prefer the Windows
        # host capture path in WSL because it captures the actual visible desktop.
        providers = [wsl_provider, X11Provider(), WaylandProvider(), GenericProvider()]
    elif desktop == DesktopEnvironment.X11:
        providers = [X11Provider(), GenericProvider()]
    elif desktop == DesktopEnvironment.WAYLAND:
        providers = [WaylandProvider(), GenericProvider()]
    else:
        providers = [X11Provider(), WaylandProvider(), GenericProvider()]

    for provider in providers:
        if provider.available:
            return provider

    raise ProviderNotAvailableError(
        "No screenshot provider available. "
        "Install: grim (Wayland), imagemagick (X11), "
        "or spectacle/flameshot (generic).",
    )
