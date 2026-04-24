"""Abstract base class for screenshot providers."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class ScreenshotProvider(ABC):
    """Abstract base class defining the screenshot provider interface."""

    @abstractmethod
    def capture_screen(self, output_path: str, display: int = 0) -> str:
        """Capture full screen. Returns path to saved image."""
        ...

    @abstractmethod
    def capture_window(self, output_path: str, window_id: Optional[str] = None) -> str:
        """Capture a specific window or active window. Returns path."""
        ...

    @abstractmethod
    def capture_region(self, output_path: str, x: int, y: int, width: int, height: int) -> str:
        """Capture a screen region. Returns path."""
        ...

    @abstractmethod
    def list_windows(self) -> List[Dict[str, Any]]:
        """List available windows with IDs and titles."""
        ...

    @abstractmethod
    def list_screens(self) -> List[Dict[str, Any]]:
        """List available screens/displays."""
        ...

    @property
    @abstractmethod
    def available(self) -> bool:
        """Whether this provider is available on the current system."""
        ...
