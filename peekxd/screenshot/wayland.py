"""Removed screenshot provider stub.

Visible screenshot capture was removed from PeekXD because it can trigger
portal/fullscreen prompts and disturb the user's live desktop. Use
``peekxd see --semantic`` for non-visual state.
"""

from .base import ScreenshotProvider
from ..core.errors import ScreenshotError

_REMOVED = "Visible screenshot capture is removed from PeekXD; use `peekxd see --semantic`."


class WaylandProvider(ScreenshotProvider):
    """Compatibility stub that never captures pixels."""

    permission_label = "removed"

    @property
    def available(self) -> bool:
        return False

    def capture_screen(self, output_path: str, display: int = 0) -> str:
        del output_path, display
        raise ScreenshotError(_REMOVED)

    def capture_window(self, output_path: str, window_id=None) -> str:
        del output_path, window_id
        raise ScreenshotError(_REMOVED)

    def capture_region(self, output_path: str, x: int, y: int, width: int, height: int) -> str:
        del output_path, x, y, width, height
        raise ScreenshotError(_REMOVED)

    def list_windows(self):
        return []

    def list_screens(self):
        return []

    @classmethod
    def is_available(cls) -> bool:
        return False
