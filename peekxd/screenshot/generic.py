"""Generic screenshot provider using spectacle, flameshot, or gnome-screenshot."""

from typing import Any, Dict, List

from ..core.errors import ScreenshotError
from ..core.utils import executable_available, run_command
from .base import ScreenshotProvider


class GenericProvider(ScreenshotProvider):
    """Generic screenshot provider using common desktop tools.

    Supports:
    - spectacle (KDE)
    - flameshot
    - gnome-screenshot
    """

    # ------------------------------------------------------------------
    # Core capture methods
    # ------------------------------------------------------------------

    def capture_screen(self, output_path: str, display: int = 0) -> str:
        """Capture the full screen using the best available tool."""
        if executable_available("spectacle"):
            run_command(["spectacle", "-b", "-o", output_path])
        elif executable_available("flameshot"):
            run_command(["flameshot", "full", "-p", output_path])
        elif executable_available("gnome-screenshot"):
            run_command(["gnome-screenshot", "-f", output_path])
        else:
            raise ScreenshotError(
                "No generic screenshot tool available. "
                "Install spectacle (KDE), flameshot, or gnome-screenshot.",
            )
        return output_path

    def capture_window(self, output_path: str, window_id=None) -> str:
        """Capture the active window using the best available tool.

        The *window_id* parameter is accepted for API compatibility but is
        ignored by all underlying generic tools; they always capture the
        active/focused window.
        """
        if executable_available("spectacle"):
            run_command(["spectacle", "-b", "-a", "-o", output_path])
        elif executable_available("flameshot"):
            # flameshot gui can capture a selected window interactively;
            # for non-interactive active window, fall through to gnome-screenshot
            # or use full screen as best-effort fallback.
            if executable_available("gnome-screenshot"):
                run_command(["gnome-screenshot", "-w", "-f", output_path])
            else:
                run_command(["flameshot", "full", "-p", output_path])
        elif executable_available("gnome-screenshot"):
            run_command(["gnome-screenshot", "-w", "-f", output_path])
        else:
            raise ScreenshotError(
                "No generic screenshot tool available. "
                "Install spectacle (KDE), flameshot, or gnome-screenshot.",
            )
        return output_path

    def capture_region(self, output_path: str, x: int, y: int, width: int, height: int) -> str:
        """Capture a screen region.

        For generic tools, region capture is best-effort:
        - spectacle: built-in region mode (interactive)
        - flameshot: gui mode (interactive)
        - gnome-screenshot: area mode (interactive)

        Falls back to full-screen capture if interactive capture fails.
        """
        if executable_available("spectacle"):
            run_command(["spectacle", "-b", "-r", "-o", output_path])
        elif executable_available("flameshot"):
            run_command(["flameshot", "gui", "-p", output_path])
        elif executable_available("gnome-screenshot"):
            run_command(["gnome-screenshot", "-a", "-f", output_path])
        else:
            raise ScreenshotError(
                "No generic screenshot tool available. "
                "Install spectacle (KDE), flameshot, or gnome-screenshot.",
            )
        return output_path

    # ------------------------------------------------------------------
    # Window / screen introspection
    # ------------------------------------------------------------------

    def list_windows(self) -> List[Dict[str, Any]]:
        """Window listing is not supported by generic tools."""
        return []

    def list_screens(self) -> List[Dict[str, Any]]:
        """Screen listing is not supported by generic tools."""
        return []

    # ------------------------------------------------------------------
    # Availability
    # ------------------------------------------------------------------

    @property
    def available(self) -> bool:
        """True if any supported generic tool is installed."""
        return (
            executable_available("spectacle")
            or executable_available("flameshot")
            or executable_available("gnome-screenshot")
        )
