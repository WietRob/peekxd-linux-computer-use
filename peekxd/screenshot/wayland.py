"""Wayland screenshot provider using ``grim`` or ``wayshot``."""

import json
import re
from typing import Any, Dict, List, Optional

from ..core.errors import ScreenshotError
from ..core.utils import executable_available, run_command
from .base import ScreenshotProvider


class WaylandProvider(ScreenshotProvider):
    """Screenshot provider for Wayland sessions using grim or wayshot."""

    # ------------------------------------------------------------------
    # Core capture methods
    # ------------------------------------------------------------------

    def capture_screen(self, output_path: str, display: int = 0) -> str:
        """Capture the full Wayland screen.

        Uses ``grim`` if available, falling back to ``wayshot``.
        The *display* argument is accepted for API compatibility but is
        ignored by both underlying tools.
        """
        if executable_available("grim"):
            run_command(["grim", output_path])
        elif executable_available("wayshot"):
            run_command(["wayshot", "-f", output_path])
        else:
            raise ScreenshotError(
                "No Wayland capture tool available. Install grim or wayshot.",
            )
        return output_path

    def capture_window(self, output_path: str, window_id: Optional[str] = None) -> str:
        """Capture a specific Wayland window or the active window.

        Retrieves window geometry via ``swaymsg`` or ``wlrctl`` and then
        uses ``grim -g`` to capture that region.
        """
        geometry = None

        if window_id:
            geometry = self._get_window_geometry_by_id(window_id)

        if geometry is None:
            geometry = self._get_active_window_geometry()

        if geometry is None:
            raise ScreenshotError(
                "Could not determine window geometry. "
                "Ensure swaymsg (Sway) or wlrctl is installed.",
            )

        geo_str = f"{geometry['x']},{geometry['y']} {geometry['width']}x{geometry['height']}"

        if executable_available("grim"):
            run_command(["grim", "-g", geo_str, output_path])
        elif executable_available("wayshot"):
            run_command([
                "wayshot", "-f", output_path,
                "-s", geo_str,
            ])
        else:
            raise ScreenshotError(
                "No Wayland capture tool available. Install grim or wayshot.",
            )
        return output_path

    def capture_region(self, output_path: str, x: int, y: int, width: int, height: int) -> str:
        """Capture a rectangular region of the Wayland screen."""
        geo_str = f"{x},{y} {width}x{height}"

        if executable_available("grim"):
            run_command(["grim", "-g", geo_str, output_path])
        elif executable_available("wayshot"):
            run_command(["wayshot", "-f", output_path, "-s", geo_str])
        else:
            raise ScreenshotError(
                "No Wayland capture tool available. Install grim or wayshot.",
            )
        return output_path

    # ------------------------------------------------------------------
    # Window / screen introspection
    # ------------------------------------------------------------------

    def list_windows(self) -> List[Dict[str, Any]]:
        """List available Wayland windows using swaymsg or wlrctl."""
        windows: List[Dict[str, Any]] = []

        if executable_available("swaymsg"):
            try:
                result = run_command(["swaymsg", "-t", "get_tree"], check=True)
                tree = json.loads(result.stdout)
                windows = self._extract_sway_windows(tree)
            except Exception:
                pass
        elif executable_available("wlrctl"):
            try:
                result = run_command(["wlrctl", "window", "list"], check=False)
                if result.returncode == 0:
                    windows = self._parse_wlrctl_windows(result.stdout)
            except Exception:
                pass

        return windows

    def list_screens(self) -> List[Dict[str, Any]]:
        """List available Wayland outputs using swaymsg or grim."""
        screens: List[Dict[str, Any]] = []

        if executable_available("swaymsg"):
            try:
                result = run_command(["swaymsg", "-t", "get_outputs"], check=True)
                outputs = json.loads(result.stdout)
                for out in outputs:
                    if not isinstance(out, dict):
                        continue
                    rect = out.get("rect", {})
                    screens.append({
                        "name": out.get("name", "unknown"),
                        "width": rect.get("width", 0),
                        "height": rect.get("height", 0),
                        "x": rect.get("x", 0),
                        "y": rect.get("y", 0),
                        "active": out.get("active", False),
                        "primary": out.get("primary", False),
                    })
            except Exception:
                pass
        elif executable_available("grim"):
            try:
                result = run_command(["grim", "-l"], check=True)
                screens = self._parse_grim_outputs(result.stdout)
            except Exception:
                pass

        return screens

    # ------------------------------------------------------------------
    # Availability
    # ------------------------------------------------------------------

    @property
    def available(self) -> bool:
        """True if either ``grim`` or ``wayshot`` is installed."""
        return executable_available("grim") or executable_available("wayshot")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_active_window_geometry() -> Optional[Dict[str, int]]:
        """Get geometry of the currently focused Wayland window."""
        if executable_available("swaymsg"):
            try:
                result = run_command(["swaymsg", "-t", "get_tree"], check=True)
                tree = json.loads(result.stdout)
                focused = WaylandProvider._find_focused(tree)
                if focused and "rect" in focused:
                    rect = focused["rect"]
                    return {
                        "x": rect.get("x", 0),
                        "y": rect.get("y", 0),
                        "width": rect.get("width", 0),
                        "height": rect.get("height", 0),
                    }
            except Exception:
                pass

        if executable_available("wlrctl"):
            try:
                result = run_command(["wlrctl", "window", "find", "focused"], check=False)
                if result.returncode == 0:
                    return WaylandProvider._parse_wlrctl_geometry(result.stdout)
            except Exception:
                pass

        return None

    @staticmethod
    def _get_window_geometry_by_id(window_id: str) -> Optional[Dict[str, int]]:
        """Get geometry of a specific Wayland window by ID."""
        if executable_available("swaymsg"):
            try:
                result = run_command(["swaymsg", "-t", "get_tree"], check=True)
                tree = json.loads(result.stdout)
                window = WaylandProvider._find_window_by_id(tree, window_id)
                if window and "rect" in window:
                    rect = window["rect"]
                    return {
                        "x": rect.get("x", 0),
                        "y": rect.get("y", 0),
                        "width": rect.get("width", 0),
                        "height": rect.get("height", 0),
                    }
            except Exception:
                pass
        return None

    @staticmethod
    def _find_focused(node: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Recursively find the focused window in a swaymsg tree."""
        if node.get("focused"):
            return node
        for child in node.get("nodes", []):
            result = WaylandProvider._find_focused(child)
            if result:
                return result
        for child in node.get("floating_nodes", []):
            result = WaylandProvider._find_focused(child)
            if result:
                return result
        return None

    @staticmethod
    def _find_window_by_id(node: Dict[str, Any], window_id: str) -> Optional[Dict[str, Any]]:
        """Recursively find a window by its ID in a swaymsg tree."""
        if str(node.get("id", "")) == window_id:
            return node
        for child in node.get("nodes", []):
            result = WaylandProvider._find_window_by_id(child, window_id)
            if result:
                return result
        for child in node.get("floating_nodes", []):
            result = WaylandProvider._find_window_by_id(child, window_id)
            if result:
                return result
        return None

    @staticmethod
    def _extract_sway_windows(tree: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract all windows from a swaymsg tree."""
        windows: List[Dict[str, Any]] = []
        for node in tree.get("nodes", []):
            windows.extend(WaylandProvider._extract_sway_windows(node))
        for node in tree.get("floating_nodes", []):
            windows.extend(WaylandProvider._extract_sway_windows(node))
        if tree.get("app_id") or tree.get("window_properties"):
            windows.append({
                "id": str(tree.get("id", "")),
                "app_id": tree.get("app_id", ""),
                "name": tree.get("name", ""),
                "title": tree.get("window_properties", {}).get("title", ""),
                "class": tree.get("window_properties", {}).get("class", ""),
            })
        return windows

    @staticmethod
    def _parse_wlrctl_windows(output: str) -> List[Dict[str, Any]]:
        """Parse ``wlrctl window list`` output into window dicts."""
        windows: List[Dict[str, Any]] = []
        for line in output.strip().splitlines():
            parts = line.strip().split(None, 1)
            if parts:
                windows.append({"id": parts[0], "title": parts[1] if len(parts) > 1 else ""})
        return windows

    @staticmethod
    def _parse_wlrctl_geometry(output: str) -> Optional[Dict[str, int]]:
        """Parse window geometry from ``wlrctl`` output."""
        x = y = w = h = 0
        for line in output.strip().splitlines():
            match = re.match(r"\s*(x|y|width|height):\s*(\d+)", line)
            if match:
                key, val = match.group(1), int(match.group(2))
                if key == "x":
                    x = val
                elif key == "y":
                    y = val
                elif key == "width":
                    w = val
                elif key == "height":
                    h = val
        if w > 0 and h > 0:
            return {"x": x, "y": y, "width": w, "height": h}
        return None

    @staticmethod
    def _parse_grim_outputs(output: str) -> List[Dict[str, Any]]:
        """Parse ``grim -l`` output into screen dicts."""
        screens: List[Dict[str, Any]] = []
        for line in output.strip().splitlines():
            parts = line.split()
            if len(parts) >= 2:
                name = parts[0]
                geo_match = re.match(r"(\d+)x(\d+)\+(\d+)\+(\d+)", parts[1])
                if geo_match:
                    screens.append({
                        "name": name,
                        "width": int(geo_match.group(1)),
                        "height": int(geo_match.group(2)),
                        "x": int(geo_match.group(3)),
                        "y": int(geo_match.group(4)),
                    })
                else:
                    screens.append({"name": name})
            elif parts:
                screens.append({"name": parts[0]})
        return screens
