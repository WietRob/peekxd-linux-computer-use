"""Wayland window management provider using wlrctl or swaymsg."""

import json
import re
import subprocess
from typing import Any, Dict, List, Optional

from peekxd.core.utils import executable_available, run_command
from peekxd.core.errors import WindowError
from peekxd.window.base import WindowProvider


class WaylandWindowProvider(WindowProvider):
    """Window provider for wlroots-based Wayland compositors.

    Prefers ``wlrctl`` for generic wlroots support, with ``swaymsg`` as
    a fallback for Sway and i3-compatible compositors.
    """

    def __init__(self) -> None:
        """Determine which backend to use."""
        self._has_wlrctl = executable_available("wlrctl")
        self._has_swaymsg = executable_available("swaymsg")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _run_wlrctl(args: list[str], check: bool = True, timeout: float = 10.0) -> subprocess.CompletedProcess:
        """Run a wlrctl command.

        Args:
            args: Arguments to pass to wlrctl.
            check: Whether to raise WindowError on non-zero exit.
            timeout: Maximum time to wait.

        Returns:
            CompletedProcess instance.

        Raises:
            WindowError: If wlrctl is not found or returns an error.
        """
        cmd = ["wlrctl", *args]
        try:
            result = run_command(cmd, check=False, timeout=timeout)
        except Exception as exc:
            raise WindowError(f"wlrctl command failed: {' '.join(cmd)}", details={"error": str(exc)}) from exc

        if check and result.returncode != 0:
            stderr = result.stderr.strip() if result.stderr else ""
            raise WindowError(
                f"wlrctl failed (exit {result.returncode}): {' '.join(cmd)}",
                details={"stderr": stderr, "command": cmd},
            )
        return result

    @staticmethod
    def _run_swaymsg(args: list[str], check: bool = True, timeout: float = 10.0) -> subprocess.CompletedProcess:
        """Run a swaymsg command.

        Args:
            args: Arguments to pass to swaymsg.
            check: Whether to raise WindowError on non-zero exit.
            timeout: Maximum time to wait.

        Returns:
            CompletedProcess instance.

        Raises:
            WindowError: If swaymsg is not found or returns an error.
        """
        cmd = ["swaymsg", *args]
        try:
            result = run_command(cmd, check=False, timeout=timeout)
        except Exception as exc:
            raise WindowError(f"swaymsg command failed: {' '.join(cmd)}", details={"error": str(exc)}) from exc

        if check and result.returncode != 0:
            stderr = result.stderr.strip() if result.stderr else ""
            raise WindowError(
                f"swaymsg failed (exit {result.returncode}): {' '.join(cmd)}",
                details={"stderr": stderr, "command": cmd},
            )
        return result

    @staticmethod
    def _parse_sway_tree(tree: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Recursively parse swaymsg tree to extract visible windows.

        Args:
            tree: The JSON tree returned by ``swaymsg -t get_tree``.

        Returns:
            Flat list of window dictionaries.
        """
        windows: List[Dict[str, Any]] = []

        def _walk(node: Dict[str, Any]) -> None:
            if not isinstance(node, dict):
                return

            # A window node typically has an 'app_id' or 'window_properties'
            node_type = node.get("type", "")
            node_layout = node.get("layout", "")
            name = node.get("name", "") or ""

            # Filter out workspace and container nodes without actual windows
            if node_type in ("con", "floating_con") and name:
                wid = str(node.get("id", ""))
                rect = node.get("rect", {})
                window_rect = node.get("window_rect", {})

                # Use window_rect for content area, rect for position
                x = rect.get("x", 0) if rect else 0
                y = rect.get("y", 0) if rect else 0
                width = window_rect.get("width", rect.get("width", 0)) if window_rect else rect.get("width", 0)
                height = window_rect.get("height", rect.get("height", 0)) if window_rect else rect.get("height", 0)

                # Only include actual application windows (not empty containers)
                app_id = node.get("app_id", "") or ""
                window_props = node.get("window_properties", {})
                class_name = window_props.get("class", "") if window_props else ""
                title = window_props.get("title", "") if window_props else name

                if app_id or class_name or title:
                    windows.append(
                        {
                            "id": wid,
                            "name": title or name,
                            "app_id": app_id,
                            "class": class_name,
                            "x": x,
                            "y": y,
                            "width": width,
                            "height": height,
                        }
                    )

            # Recurse into children
            for child in node.get("nodes", []):
                _walk(child)
            for child in node.get("floating_nodes", []):
                _walk(child)

        _walk(tree)
        return windows

    @staticmethod
    def _parse_sway_active(tree: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Find the focused window in a swaymsg tree.

        Args:
            tree: The JSON tree returned by ``swaymsg -t get_tree``.

        Returns:
            The focused window dict, or None.
        """
        def _walk(node: Dict[str, Any]) -> Optional[Dict[str, Any]]:
            if not isinstance(node, dict):
                return None

            if node.get("focused", False):
                wid = str(node.get("id", ""))
                rect = node.get("rect", {})
                window_rect = node.get("window_rect", {})
                name = node.get("name", "") or ""
                app_id = node.get("app_id", "") or ""
                window_props = node.get("window_properties", {})
                title = window_props.get("title", "") if window_props else name

                return {
                    "id": wid,
                    "name": title or name,
                    "app_id": app_id,
                    "x": rect.get("x", 0),
                    "y": rect.get("y", 0),
                    "width": window_rect.get("width", rect.get("width", 0)),
                    "height": window_rect.get("height", rect.get("height", 0)),
                }

            for child in node.get("nodes", []):
                result = _walk(child)
                if result:
                    return result
            for child in node.get("floating_nodes", []):
                result = _walk(child)
                if result:
                    return result
            return None

        return _walk(tree)

    def _list_wlrctl(self) -> List[Dict[str, Any]]:
        """List windows using wlrctl.

        Parses the ``wlrctl window list`` output.

        Returns:
            List of window dictionaries.
        """
        result = self._run_wlrctl(["window", "list"], check=False, timeout=10.0)
        if result.returncode != 0 or not result.stdout.strip():
            return []

        windows: List[Dict[str, Any]] = []
        for line in result.stdout.strip().splitlines():
            line = line.strip()
            if not line:
                continue

            # Expected format varies; try to extract app_id and title
            # Common format: "app_id: Title" or just "Title"
            parts = line.split(":", 1)
            if len(parts) == 2:
                app_id = parts[0].strip()
                title = parts[1].strip()
            else:
                app_id = ""
                title = line

            # wlrctl doesn't provide geometry; use placeholder
            windows.append(
                {
                    "id": title or app_id,
                    "name": title or app_id,
                    "app_id": app_id,
                    "x": 0,
                    "y": 0,
                    "width": 0,
                    "height": 0,
                }
            )
        return windows

    def _list_swaymsg(self) -> List[Dict[str, Any]]:
        """List windows using swaymsg.

        Returns:
            List of window dictionaries.
        """
        result = self._run_swaymsg(["-t", "get_tree"], timeout=10.0)
        try:
            tree = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise WindowError(
                "Failed to parse swaymsg tree output",
                details={"error": str(exc)},
            ) from exc
        return self._parse_sway_tree(tree)

    def _focus_wlrctl(self, window_id: str) -> None:
        """Focus a window using wlrctl.

        Args:
            window_id: The window identifier (title or app_id).
        """
        self._run_wlrctl(["window", "focus", window_id])

    def _focus_swaymsg(self, window_id: str) -> None:
        """Focus a window using swaymsg.

        Args:
            window_id: The container ID.
        """
        self._run_swaymsg([f"[con_id={window_id}]", "focus"])

    def _move_wlrctl(self, window_id: str, x: int, y: int) -> None:
        """Move a window using wlrctl.

        Args:
            window_id: The window identifier.
            x: Horizontal position.
            y: Vertical position.
        """
        self._run_wlrctl(["window", "move", window_id, str(x), str(y)])

    def _move_swaymsg(self, window_id: str, x: int, y: int) -> None:
        """Move a window using swaymsg.

        Args:
            window_id: The container ID.
            x: Horizontal position.
            y: Vertical position.
        """
        self._run_swaymsg([f"[con_id={window_id}]", "move", "position", str(x), str(y)])

    def _resize_wlrctl(self, window_id: str, width: int, height: int) -> None:
        """Resize a window using wlrctl.

        Args:
            window_id: The window identifier.
            width: New width.
            height: New height.
        """
        self._run_wlrctl(["window", "resize", window_id, str(width), str(height)])

    def _resize_swaymsg(self, window_id: str, width: int, height: int) -> None:
        """Resize a window using swaymsg.

        Args:
            window_id: The container ID.
            width: New width.
            height: New height.
        """
        self._run_swaymsg([f"[con_id={window_id}]", "resize", "set", str(width), str(height)])

    def _close_wlrctl(self, window_id: str) -> None:
        """Close a window using wlrctl.

        Args:
            window_id: The window identifier.
        """
        self._run_wlrctl(["window", "close", window_id])

    def _close_swaymsg(self, window_id: str) -> None:
        """Close a window using swaymsg.

        Args:
            window_id: The container ID.
        """
        self._run_swaymsg([f"[con_id={window_id}]", "kill"])

    def _get_active_swaymsg(self) -> Optional[Dict[str, Any]]:
        """Get the active window using swaymsg.

        Returns:
            The focused window dict, or None.
        """
        result = self._run_swaymsg(["-t", "get_tree"], timeout=10.0)
        try:
            tree = json.loads(result.stdout)
        except json.JSONDecodeError:
            return None
        return self._parse_sway_active(tree)

    # ------------------------------------------------------------------
    # WindowProvider interface
    # ------------------------------------------------------------------

    def list_windows(self) -> List[Dict[str, Any]]:
        """List all visible windows.

        Prefers ``wlrctl``, falls back to ``swaymsg``.

        Returns:
            List of window dictionaries.
        """
        if self._has_wlrctl:
            try:
                return self._list_wlrctl()
            except WindowError:
                if not self._has_swaymsg:
                    raise
        if self._has_swaymsg:
            return self._list_swaymsg()
        raise WindowError("No Wayland backend available (wlrctl or swaymsg)")

    def focus_window(self, window_id: str) -> None:
        """Focus (activate) a window.

        Prefers ``wlrctl``, falls back to ``swaymsg``.

        Args:
            window_id: The window identifier.

        Raises:
            WindowError: If the operation fails.
        """
        if self._has_wlrctl:
            try:
                self._focus_wlrctl(window_id)
                return
            except WindowError:
                if not self._has_swaymsg:
                    raise
        if self._has_swaymsg:
            self._focus_swaymsg(window_id)
            return
        raise WindowError("No Wayland backend available (wlrctl or swaymsg)")

    def move_window(self, window_id: str, x: int, y: int) -> None:
        """Move a window to the specified screen coordinates.

        Args:
            window_id: The window identifier.
            x: Horizontal position in pixels.
            y: Vertical position in pixels.

        Raises:
            WindowError: If the operation fails.
        """
        if self._has_wlrctl:
            try:
                self._move_wlrctl(window_id, x, y)
                return
            except WindowError:
                if not self._has_swaymsg:
                    raise
        if self._has_swaymsg:
            self._move_swaymsg(window_id, x, y)
            return
        raise WindowError("No Wayland backend available (wlrctl or swaymsg)")

    def resize_window(self, window_id: str, width: int, height: int) -> None:
        """Resize a window to the specified dimensions.

        Args:
            window_id: The window identifier.
            width: New width in pixels.
            height: New height in pixels.

        Raises:
            WindowError: If the operation fails.
        """
        if self._has_wlrctl:
            try:
                self._resize_wlrctl(window_id, width, height)
                return
            except WindowError:
                if not self._has_swaymsg:
                    raise
        if self._has_swaymsg:
            self._resize_swaymsg(window_id, width, height)
            return
        raise WindowError("No Wayland backend available (wlrctl or swaymsg)")

    def close_window(self, window_id: str) -> None:
        """Close a window.

        Args:
            window_id: The window identifier.

        Raises:
            WindowError: If the operation fails.
        """
        if self._has_wlrctl:
            try:
                self._close_wlrctl(window_id)
                return
            except WindowError:
                if not self._has_swaymsg:
                    raise
        if self._has_swaymsg:
            self._close_swaymsg(window_id)
            return
        raise WindowError("No Wayland backend available (wlrctl or swaymsg)")

    def get_active_window(self) -> Optional[Dict[str, Any]]:
        """Get the currently focused window.

        Uses ``swaymsg`` tree parsing (``wlrctl`` doesn't reliably
        expose focused window info).

        Returns:
            Window dictionary, or None if no window is focused.
        """
        if self._has_swaymsg:
            return self._get_active_swaymsg()
        # wlrctl has no reliable "get focused window" command;
        # try listing and hope the first entry is focused
        return None

    def launch_app(self, app_name: str) -> None:
        """Launch an application.

        Tries ``wlrctl application launch`` first, falls back to direct
        ``subprocess.Popen``.

        Args:
            app_name: The command or desktop file name to launch.

        Raises:
            WindowError: If the application cannot be launched.
        """
        if self._has_wlrctl:
            try:
                self._run_wlrctl(["application", "launch", app_name])
                return
            except WindowError:
                pass
        try:
            subprocess.Popen([app_name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as exc:
            raise WindowError(
                f"Failed to launch application: {app_name}",
                details={"error": str(exc)},
            ) from exc

    @property
    def available(self) -> bool:
        """Check if wlrctl or swaymsg is available.

        Returns:
            True if either ``wlrctl`` or ``swaymsg`` is found in PATH.
        """
        return self._has_wlrctl or self._has_swaymsg
