"""Safety package for peekxd — MCP safety middleware, overlay integration, and audit."""

from .overlay import OverlayControllerFactory, build_ghost_overlay_context

__all__ = [
    "OverlayControllerFactory",
    "build_ghost_overlay_context",
]
