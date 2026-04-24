"""X11 screenshot provider using ImageMagick ``import`` or ``xwd``."""

import json
import re
from typing import Any, Dict, List, Optional

from ..core.errors import ScreenshotError
from ..core.utils import executable_available, run_command
from .base import ScreenshotProvider


class X11Provider(ScreenshotProvider):
    """Screenshot provider for X11 sessions using ImageMagick or xwd."""

    # ------------------------------------------------------------------
    # Core capture methods
    # ------------------------------------------------------------------

    def capture_screen(self, output_path: str, display: int = 0) -> str:
        """Capture the full X11 screen.

        Uses ImageMagick's ``import`` if available, falling back to
        ``xwd`` piped through ``convert``.
        """
        if executable_available("import"):
            run_command(["import", "-window", "root", "-display", f":{display}", output_path])
        elif executable_available("xwd") and executable_available("convert"):
            run_command(
                ["xwd", "-root", "-display", f":{display}"],
                capture_output=True,
                check=True,
            )
            run_command(
                ["convert", "xwd:-", output_path],
                capture_output=True,
                check=True,
            )
        else:
            raise ScreenshotError(
                "No X11 capture tool available. Install ImageMagick (import) or xwd + convert.",
            )
        return output_path

    def capture_window(self, output_path: str, window_id: Optional[str] = None) -> str:
        """Capture a specific X11 window or the active window."""
        if window_id is None:
            window_id = self._get_active_window_id()
            if window_id is None:
                raise ScreenshotError("Could not determine active window ID.")

        if executable_available("import"):
            run_command(["import", "-window", window_id, output_path])
        elif executable_available("xwd") and executable_available("convert"):
            run_command(["xwd", "-id", window_id, "-out", "/tmp/x11_window.xwd"])
            run_command(["convert", "/tmp/x11_window.xwd", output_path])
        else:
            raise ScreenshotError(
                "No X11 capture tool available. Install ImageMagick (import) or xwd + convert.",
            )
        return output_path

    def capture_region(self, output_path: str, x: int, y: int, width: int, height: int) -> str:
        """Capture a rectangular region of the X11 screen."""
        if executable_available("import"):
            run_command(["import", "-crop", f"{width}x{height}+{x}+{y}", output_path])
        elif executable_available("xwd") and executable_available("convert"):
            run_command(["xwd", "-root", "-out", "/tmp/x11_region.xwd"])
            run_command([
                "convert", "/tmp/x11_region.xwd",
                "-crop", f"{width}x{height}+{x}+{y}",
                output_path,
            ])
        else:
            raise ScreenshotError(
                "No X11 capture tool available. Install ImageMagick (import) or xwd + convert.",
            )
        return output_path

    # ------------------------------------------------------------------
    # Window / screen introspection
    # ------------------------------------------------------------------

    def list_windows(self) -> List[Dict[str, Any]]:
        """List visible X11 windows with IDs and titles."""
        windows: List[Dict[str, Any]] = []

        if executable_available("xdotool"):
            try:
                result = run_command(
                    ["xdotool", "search", "--onlyvisible", "--class", "*"],
                    check=True,
                )
                ids = result.stdout.strip().splitlines()
                for wid in ids:
                    wid = wid.strip()
                    if not wid:
                        continue
                    title_res = run_command(
                        ["xdotool", "getwindowname", wid],
                        check=False,
                    )
                    title = title_res.stdout.strip() if title_res.returncode == 0 else ""
                    windows.append({"id": wid, "title": title})
            except Exception:
                pass
        elif executable_available("xwininfo"):
            try:
                result = run_command(["xwininfo", "-root", "-tree"], check=True)
                windows = self._parse_xwininfo_tree(result.stdout)
            except Exception:
                pass

        return windows

    def list_screens(self) -> List[Dict[str, Any]]:
        """List available X11 screens/displays using xrandr."""
        screens: List[Dict[str, Any]] = []

        if not executable_available("xrandr"):
            return screens

        try:
            result = run_command(["xrandr", "--listmonitors"], check=True)
            screens = self._parse_xrandr_monitors(result.stdout)
        except Exception:
            pass

        return screens

    # ------------------------------------------------------------------
    # Availability
    # ------------------------------------------------------------------

    @property
    def available(self) -> bool:
        """True if either ImageMagick ``import`` or ``xwd`` is installed."""
        return executable_available("import") or executable_available("xwd")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_active_window_id() -> Optional[str]:
        """Get the ID of the currently focused X11 window via xdotool."""
        if not executable_available("xdotool"):
            return None
        try:
            result = run_command(["xdotool", "getactivewindow"], check=True)
            return result.stdout.strip()
        except Exception:
            return None

    @staticmethod
    def _parse_xwininfo_tree(output: str) -> List[Dict[str, Any]]:
        """Parse ``xwininfo -root -tree`` output into window dicts."""
        windows: List[Dict[str, Any]] = []
        for line in output.splitlines():
            match = re.match(r"\s*(0x[0-9a-fA-F]+)\s+\"([^\"]*)\"", line)
            if match:
                windows.append({"id": match.group(1), "title": match.group(2)})
        return windows

    @staticmethod
    def _parse_xrandr_monitors(output: str) -> List[Dict[str, Any]]:
        """Parse ``xrandr --listmonitors`` output into screen dicts."""
        screens: List[Dict[str, Any]] = []
        for line in output.splitlines():
            # Skip header line (contains 'Monitors: N')
            if "Monitors:" in line:
                continue
            match = re.match(
                r"\s*\d+:\s*\+\*?(\S+)\s+(\d+)/(\d+)x(\d+)/(\d+)\+(\d+)\+(\d+)",
                line,
            )
            if match:
                screens.append({
                    "name": match.group(1),
                    "width": int(match.group(2)),
                    "height": int(match.group(4)),
                    "x": int(match.group(6)),
                    "y": int(match.group(7)),
                })
        return screens
