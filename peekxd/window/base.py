"""Abstract base class for window management providers."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class WindowProvider(ABC):
    """Abstract base class for window management providers.

    Implementations must provide methods for listing, focusing, moving,
    resizing, and closing windows, as well as querying the active window
    and launching applications.
    """

    @abstractmethod
    def list_windows(self) -> List[Dict[str, Any]]:
        """List all visible windows.

        Returns:
            List of dictionaries containing window information.
            Each dict should have at minimum: 'id', 'name'.
            May also include: 'x', 'y', 'width', 'height'.
        """
        ...

    @abstractmethod
    def focus_window(self, window_id: str) -> None:
        """Focus (activate) a window by its ID.

        Args:
            window_id: The unique identifier of the window.
        """
        ...

    @abstractmethod
    def move_window(self, window_id: str, x: int, y: int) -> None:
        """Move a window to the specified coordinates.

        Args:
            window_id: The unique identifier of the window.
            x: Horizontal position in pixels.
            y: Vertical position in pixels.
        """
        ...

    @abstractmethod
    def resize_window(self, window_id: str, width: int, height: int) -> None:
        """Resize a window to the specified dimensions.

        Args:
            window_id: The unique identifier of the window.
            width: New width in pixels.
            height: New height in pixels.
        """
        ...

    @abstractmethod
    def close_window(self, window_id: str) -> None:
        """Close a window by its ID.

        Sends a close request. Falls back to a forceful kill
        if the graceful close fails.

        Args:
            window_id: The unique identifier of the window.
        """
        ...

    @abstractmethod
    def get_active_window(self) -> Optional[Dict[str, Any]]:
        """Get the currently focused (active) window.

        Returns:
            Dictionary with window info, or None if no window is focused.
        """
        ...

    @abstractmethod
    def launch_app(self, app_name: str) -> None:
        """Launch an application by name.

        Args:
            app_name: The command or desktop file name of the application.
        """
        ...

    @property
    @abstractmethod
    def available(self) -> bool:
        """Whether this provider is available on the current system.

        Returns:
            True if the required tools are installed and usable.
        """
        ...
