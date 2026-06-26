"""Wayland input provider using ydotool."""

import os
from pathlib import Path

from peekxd.core.utils import run_command, executable_available
from peekxd.core.errors import InputError
from peekxd.input.base import InputProvider


# Button mapping for ydotool: 0xC0=left, 0xC1=right, 0xC2=middle
# Per ydotool documentation, we use decimal values passed as strings.
# Also used by click: 4=scroll_up, 5=scroll_down
_BUTTON_MAP = {
    "left": "0xC0",
    "right": "0xC1",
    "middle": "0xC2",
}

_SCROLL_MAP = {
    "up": "4",
    "down": "5",
    "left": "6",
    "right": "7",
}


# Known socket paths for the ydotoold daemon
_YDOTOOLD_SOCKET_PATHS = [
    "/run/ydotoold/socket",
    "/tmp/.ydotool_socket",
    "/tmp/ydotoold/socket",
]


def _ydotoold_socket_paths() -> list[str]:
    """Return ydotoold socket paths in priority order.

    Priority:
    1) Explicit override via ``PEEKXD_YDOTOOLD_SOCKET``
    2) Runtime socket from ``XDG_RUNTIME_DIR``
    3) Runtime socket derived from current UID
    4) Shared/common fallback locations
    """
    socket_override = os.environ.get("PEEKXD_YDOTOOLD_SOCKET")
    if socket_override:
        return [socket_override]

    runtime_user = os.getuid()
    paths = [f"/run/user/{runtime_user}/ydotoold/socket"]

    xdg_runtime_dir = os.environ.get("XDG_RUNTIME_DIR")
    if xdg_runtime_dir:
        paths.insert(0, os.path.join(xdg_runtime_dir, "ydotoold", "socket"))

    for path in _YDOTOOLD_SOCKET_PATHS:
        if path not in paths:
            paths.append(path)

    return paths


def _ydotoold_running() -> bool:
    """Check whether the ydotoold daemon socket is accessible.

    ydotool requires the daemon to be running in order to function.
    This checks a few common socket locations.
    """
    for path in _ydotoold_socket_paths():
        if Path(path).exists():
            return True
    return False


class WaylandInputProvider(InputProvider):
    """Input provider for Wayland sessions using ydotool.

    Requires the ``ydotool`` executable to be installed and the
    ``ydotoold`` daemon to be running.
    """

    @property
    def available(self) -> bool:
        """Return True if ydotool is installed and the daemon is running."""
        return executable_available("ydotool") and _ydotoold_running()

    def _run(self, *args: str) -> None:
        """Run a ydotool command with the given arguments.

        Args:
            *args: Arguments to pass to ydotool.

        Raises:
            InputError: If the command fails.
        """
        cmd = ["ydotool", *args]
        try:
            run_command(cmd)
        except Exception as exc:
            raise InputError(
                f"ydotool command failed: {' '.join(cmd)}",
                details={"command": cmd, "error": str(exc)},
            ) from exc

    def move_mouse(self, x: int, y: int) -> None:
        """Move the mouse cursor to (x, y).

        Args:
            x: Horizontal screen coordinate.
            y: Vertical screen coordinate.
        """
        self._run("mousemove", str(x), str(y))

    def click(self, x: int, y: int, button: str = "left") -> None:
        """Click the specified mouse button at (x, y).

        ydotool click does not accept coordinates, so we first move
        the cursor and then click.

        Args:
            x: Horizontal screen coordinate.
            y: Vertical screen coordinate.
            button: Button name ("left", "middle", or "right").
        """
        self.move_mouse(x, y)
        btn = _BUTTON_MAP.get(button, "0xC0")
        self._run("click", btn)

    def double_click(self, x: int, y: int) -> None:
        """Double-click the left mouse button at (x, y).

        Args:
            x: Horizontal screen coordinate.
            y: Vertical screen coordinate.
        """
        self.move_mouse(x, y)
        # ydotool click accepts a repeat count after the button
        self._run("click", "0xC0", "2")

    def right_click(self, x: int, y: int) -> None:
        """Right-click at (x, y).

        Args:
            x: Horizontal screen coordinate.
            y: Vertical screen coordinate.
        """
        self.click(x, y, button="right")

    def type_text(self, text: str) -> None:
        """Type the given text.

        Single quotes in the text are escaped to prevent shell issues.

        Args:
            text: The text to type.
        """
        # Escape single quotes for shell safety: ' -> '\''
        escaped = text.replace("'", "'\"'\"'")
        self._run("type", escaped)

    def key_press(self, key: str) -> None:
        """Press and release a single key.

        Args:
            key: Key name (e.g., "Return", "Escape").
        """
        self._run("key", key)

    def hotkey(self, *keys: str) -> None:
        """Press a key combination simultaneously.

        ydotool uses ``,`` (comma) to separate keys in a chord,
        unlike xdotool which uses ``+``.

        Args:
            *keys: Key names (e.g., "ctrl", "alt", "t").
        """
        chord = ",".join(keys)
        self._run("key", chord)

    def scroll(self, direction: str = "down", amount: int = 3) -> None:
        """Scroll the mouse wheel.

        Args:
            direction: Scroll direction ("down", "up", "left", or "right").
            amount: Number of scroll clicks.
        """
        btn_num = _SCROLL_MAP.get(direction, "5")
        for _ in range(amount):
            self._run("click", btn_num)

    def drag(self, x1: int, y1: int, x2: int, y2: int) -> None:
        """Drag the mouse from (x1, y1) to (x2, y2).

        ydotool does not support chaining in a single invocation,
        so we issue separate commands for each step.

        Args:
            x1: Starting x coordinate.
            y1: Starting y coordinate.
            x2: Ending x coordinate.
            y2: Ending y coordinate.
        """
        self._run("mousemove", str(x1), str(y1))
        self._run("mousedown", "0xC0")
        self._run("mousemove", str(x2), str(y2))
        self._run("mouseup", "0xC0")
