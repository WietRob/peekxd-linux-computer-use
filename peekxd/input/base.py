"""Abstract base class for input providers."""

from abc import ABC, abstractmethod


class InputProvider(ABC):
    """Abstract base class for platform-specific input providers.

    All input providers must implement these methods to simulate
    mouse and keyboard interactions on Linux.
    """

    @abstractmethod
    def move_mouse(self, x: int, y: int) -> None:
        """Move the mouse cursor to the specified screen coordinates.

        Args:
            x: Horizontal screen coordinate in pixels.
            y: Vertical screen coordinate in pixels.
        """
        ...

    @abstractmethod
    def click(self, x: int, y: int, button: str = "left") -> None:
        """Click the mouse at the specified coordinates.

        Args:
            x: Horizontal screen coordinate in pixels.
            y: Vertical screen coordinate in pixels.
            button: Mouse button to click ("left", "middle", or "right").
                    Defaults to "left".
        """
        ...

    @abstractmethod
    def double_click(self, x: int, y: int) -> None:
        """Double-click the left mouse button at the specified coordinates.

        Args:
            x: Horizontal screen coordinate in pixels.
            y: Vertical screen coordinate in pixels.
        """
        ...

    @abstractmethod
    def right_click(self, x: int, y: int) -> None:
        """Right-click the mouse at the specified coordinates.

        Args:
            x: Horizontal screen coordinate in pixels.
            y: Vertical screen coordinate in pixels.
        """
        ...

    @abstractmethod
    def type_text(self, text: str) -> None:
        """Type the given text as keyboard input.

        Args:
            text: The text string to type.
        """
        ...

    @abstractmethod
    def key_press(self, key: str) -> None:
        """Press and release a single key.

        Args:
            key: The key name (e.g., "Return", "Escape", "Tab", "a").
        """
        ...

    @abstractmethod
    def hotkey(self, *keys: str) -> None:
        """Press a combination of keys simultaneously (hotkey).

        Args:
            *keys: Variable number of key names (e.g., "ctrl", "alt", "t").
        """
        ...

    @abstractmethod
    def scroll(self, direction: str = "down", amount: int = 3) -> None:
        """Scroll the mouse wheel in the given direction.

        Args:
            direction: Direction to scroll ("down", "up", "left", or "right").
                       Defaults to "down".
            amount: Number of scroll clicks. Defaults to 3.
        """
        ...

    @abstractmethod
    def drag(self, x1: int, y1: int, x2: int, y2: int) -> None:
        """Drag the mouse from one point to another.

        Performs a click-and-drag operation by holding the left mouse
        button down while moving from (x1, y1) to (x2, y2).

        Args:
            x1: Starting horizontal screen coordinate.
            y1: Starting vertical screen coordinate.
            x2: Ending horizontal screen coordinate.
            y2: Ending vertical screen coordinate.
        """
        ...

    @property
    @abstractmethod
    def available(self) -> bool:
        """Return True if this input provider is available on the system."""
        ...
