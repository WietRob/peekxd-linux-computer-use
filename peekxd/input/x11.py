"""X11 input provider using xdotool."""

import shlex
from typing import Optional

from peekxd.core.utils import run_command, executable_available
from peekxd.core.errors import InputError
from peekxd.input.base import InputProvider


# Button mapping for xdotool: 1=left, 2=middle, 3=right,
# 4=scroll_up, 5=scroll_down, 6=scroll_left, 7=scroll_right
_BUTTON_MAP = {
    "left": 1,
    "middle": 2,
    "right": 3,
}

_SCROLL_MAP = {
    "up": 4,
    "down": 5,
    "left": 6,
    "right": 7,
}

# Reverse mapping for xdotool click --repeat (needs button number)
# left and right are handled as special cases with click --repeat


class X11InputProvider(InputProvider):
    """Input provider for X11 sessions using xdotool.

    Requires the ``xdotool`` executable to be installed and available
    on PATH. All coordinates are in screen pixels.
    """

    def __init__(self) -> None:
        self._xdotool: Optional[str] = executable_available.__wrapped__("xdotool") if hasattr(executable_available, "__wrapped__") else None

    @property
    def available(self) -> bool:
        """Return True if xdotool is installed on the system."""
        return executable_available("xdotool")

    def _run(self, *args: str) -> None:
        """Run an xdotool command with the given arguments.

        Args:
            *args: Arguments to pass to xdotool.

        Raises:
            InputError: If the command fails.
        """
        cmd = ["xdotool", *args]
        try:
            run_command(cmd)
        except Exception as exc:
            raise InputError(
                f"xdotool command failed: {' '.join(cmd)}",
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

        Args:
            x: Horizontal screen coordinate.
            y: Vertical screen coordinate.
            button: Button name ("left", "middle", or "right").
        """
        btn_num = _BUTTON_MAP.get(button, 1)
        self._run("mousemove", str(x), str(y), "click", str(btn_num))

    def double_click(self, x: int, y: int) -> None:
        """Double-click the left mouse button at (x, y).

        Args:
            x: Horizontal screen coordinate.
            y: Vertical screen coordinate.
        """
        self._run("mousemove", str(x), str(y), "click", "--repeat", "2", "1")

    def right_click(self, x: int, y: int) -> None:
        """Right-click at (x, y).

        Args:
            x: Horizontal screen coordinate.
            y: Vertical screen coordinate.
        """
        self.click(x, y, button="right")

    def type_text(self, text: str) -> None:
        """Type the given text with a small delay between keystrokes.

        Single quotes in the text are escaped to prevent shell issues.

        Args:
            text: The text to type.
        """
        # Escape single quotes for shell safety: ' -> '\''
        escaped = text.replace("'", "'\"'\"'")
        self._run("type", "--delay", "10", escaped)

    def key_press(self, key: str) -> None:
        """Press and release a single key.

        Args:
            key: Key name (e.g., "Return", "Escape", "ctrl").
        """
        self._run("key", key)

    def hotkey(self, *keys: str) -> None:
        """Press a key combination simultaneously.

        xdotool uses ``+`` to separate keys in a chord.

        Args:
            *keys: Key names (e.g., "ctrl", "alt", "t").
        """
        chord = "+".join(keys)
        self._run("key", chord)

    def scroll(self, direction: str = "down", amount: int = 3) -> None:
        """Scroll the mouse wheel.

        Args:
            direction: Scroll direction ("down", "up", "left", or "right").
            amount: Number of scroll clicks.
        """
        btn_num = _SCROLL_MAP.get(direction, 5)
        for _ in range(amount):
            self._run("click", str(btn_num))

    def drag(self, x1: int, y1: int, x2: int, y2: int) -> None:
        """Drag the mouse from (x1, y1) to (x2, y2).

        Performs a left-button click-and-drag.

        Args:
            x1: Starting x coordinate.
            y1: Starting y coordinate.
            x2: Ending x coordinate.
            y2: Ending y coordinate.
        """
        self._run(
            "mousemove",
            str(x1),
            str(y1),
            "mousedown",
            "1",
            "mousemove",
            str(x2),
            str(y2),
            "mouseup",
            "1",
        )
