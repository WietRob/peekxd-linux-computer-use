"""X11 window management provider using xdotool and xprop."""

import re
import subprocess
from typing import Any, Dict, List, Optional

from peekxd.core.utils import executable_available, run_command
from peekxd.core.errors import WindowError
from peekxd.window.base import WindowProvider


class X11WindowProvider(WindowProvider):
    """Window provider for X11 desktop environments.

    Uses ``xdotool`` for window operations and ``xprop`` as a fallback
    for property queries. Requires the ``DISPLAY`` environment variable.
    """

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _run_xdotool(args: list[str], check: bool = True, timeout: float = 10.0) -> subprocess.CompletedProcess:
        """Run an xdotool command.

        Args:
            args: Arguments to pass to xdotool (after the base command).
            check: Whether to raise WindowError on non-zero exit.
            timeout: Maximum time to wait.

        Returns:
            CompletedProcess instance.

        Raises:
            WindowError: If xdotool is not found or returns an error.
        """
        cmd = ["xdotool", *args]
        try:
            result = run_command(cmd, check=False, timeout=timeout)
        except Exception as exc:
            raise WindowError(f"xdotool command failed: {' '.join(cmd)}", details={"error": str(exc)}) from exc

        if check and result.returncode != 0:
            stderr = result.stderr.strip() if result.stderr else ""
            raise WindowError(
                f"xdotool failed (exit {result.returncode}): {' '.join(cmd)}",
                details={"stderr": stderr, "command": cmd},
            )
        return result

    @staticmethod
    def _get_window_name(window_id: str) -> str:
        """Get the human-readable name of a window.

        Args:
            window_id: The numeric window ID.

        Returns:
            The window title, or an empty string if unavailable.
        """
        try:
            result = X11WindowProvider._run_xdotool(
                ["getwindowname", window_id], check=False, timeout=5.0
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return ""

    @staticmethod
    def _get_window_geometry(window_id: str) -> Dict[str, int]:
        """Parse the geometry output from ``xdotool getwindowgeometry``.

        Expected format::

            Window 12345678
              Position: 100,200 (screen: 0)
              Geometry: 800x600

        Args:
            window_id: The numeric window ID.

        Returns:
            Dictionary with keys 'x', 'y', 'width', 'height'.
        """
        geometry = {"x": 0, "y": 0, "width": 0, "height": 0}
        try:
            result = X11WindowProvider._run_xdotool(
                ["getwindowgeometry", window_id], check=False, timeout=5.0
            )
            if result.returncode != 0:
                return geometry

            output = result.stdout
            pos_match = re.search(r"Position:\s*(\d+),(\d+)", output)
            if pos_match:
                geometry["x"] = int(pos_match.group(1))
                geometry["y"] = int(pos_match.group(2))

            geo_match = re.search(r"Geometry:\s*(\d+)x(\d+)", output)
            if geo_match:
                geometry["width"] = int(geo_match.group(1))
                geometry["height"] = int(geo_match.group(2))
        except Exception:
            pass
        return geometry

    # ------------------------------------------------------------------
    # WindowProvider interface
    # ------------------------------------------------------------------

    def list_windows(self) -> List[Dict[str, Any]]:
        """List all visible windows.

        Returns:
            List of window dictionaries with keys:
            'id', 'name', 'x', 'y', 'width', 'height'.
        """
        result = self._run_xdotool(
            ["search", "--onlyvisible", ".*"], check=False, timeout=15.0
        )
        if result.returncode != 0 or not result.stdout.strip():
            return []

        windows: List[Dict[str, Any]] = []
        for line in result.stdout.strip().splitlines():
            wid = line.strip()
            if not wid or not wid.isdigit():
                continue
            name = self._get_window_name(wid)
            geo = self._get_window_geometry(wid)
            windows.append(
                {
                    "id": wid,
                    "name": name,
                    "x": geo["x"],
                    "y": geo["y"],
                    "width": geo["width"],
                    "height": geo["height"],
                }
            )
        return windows

    def focus_window(self, window_id: str) -> None:
        """Focus (activate) a window.

        Args:
            window_id: The numeric X11 window ID.

        Raises:
            WindowError: If the operation fails.
        """
        self._run_xdotool(["windowactivate", window_id])

    def move_window(self, window_id: str, x: int, y: int) -> None:
        """Move a window to the specified screen coordinates.

        Args:
            window_id: The numeric X11 window ID.
            x: Horizontal position in pixels.
            y: Vertical position in pixels.

        Raises:
            WindowError: If the operation fails.
        """
        self._run_xdotool(["windowmove", window_id, str(x), str(y)])

    def resize_window(self, window_id: str, width: int, height: int) -> None:
        """Resize a window to the specified dimensions.

        Args:
            window_id: The numeric X11 window ID.
            width: New width in pixels.
            height: New height in pixels.

        Raises:
            WindowError: If the operation fails.
        """
        self._run_xdotool(["windowsize", window_id, str(width), str(height)])

    def close_window(self, window_id: str) -> None:
        """Close a window (gracefully, with kill fallback).

        Args:
            window_id: The numeric X11 window ID.

        Raises:
            WindowError: If both close and kill fail.
        """
        try:
            self._run_xdotool(["windowclose", window_id])
        except WindowError:
            self._run_xdotool(["windowkill", window_id])

    def get_active_window(self) -> Optional[Dict[str, Any]]:
        """Get the currently focused window.

        Returns:
            Window dictionary with 'id', 'name', 'x', 'y', 'width', 'height',
            or None if there is no active window.
        """
        try:
            result = self._run_xdotool(["getactivewindow"], timeout=5.0)
        except WindowError:
            return None

        wid = result.stdout.strip()
        if not wid or not wid.isdigit():
            return None

        name = self._get_window_name(wid)
        geo = self._get_window_geometry(wid)
        return {
            "id": wid,
            "name": name,
            "x": geo["x"],
            "y": geo["y"],
            "width": geo["width"],
            "height": geo["height"],
        }

    def launch_app(self, app_name: str) -> None:
        """Launch an application.

        Tries ``xdotool exec`` first, falls back to direct subprocess.

        Args:
            app_name: The command to execute.

        Raises:
            WindowError: If the application cannot be launched.
        """
        try:
            self._run_xdotool(["exec", app_name])
        except WindowError:
            try:
                subprocess.Popen([app_name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception as exc:
                raise WindowError(
                    f"Failed to launch application: {app_name}",
                    details={"error": str(exc)},
                ) from exc

    @property
    def available(self) -> bool:
        """Check if xdotool is available.

        Returns:
            True if ``xdotool`` is found in PATH.
        """
        return executable_available("xdotool")
