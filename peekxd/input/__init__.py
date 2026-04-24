"""Input simulation module for peekxd Linux.

Provides cross-platform (X11/Wayland) input simulation capabilities
for mouse and keyboard interactions.
"""

from peekxd.input.base import InputProvider
from peekxd.input.x11 import X11InputProvider
from peekxd.input.wayland import WaylandInputProvider
from peekxd.input.detector import get_input_provider

__all__ = [
    "InputProvider",
    "X11InputProvider",
    "WaylandInputProvider",
    "get_input_provider",
]
