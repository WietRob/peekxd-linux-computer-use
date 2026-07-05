"""Overlay controller factory and context builder for SafetyMiddleware (V4).

Provides:
- OverlayControllerFactory: a callable that lazily constructs GhostOverlayController.
- build_ghost_overlay_context: enriches an OverlayRequest with snapshot element context.

This module bridges the core overlay module (peekxd.core.overlay) with the
safety middleware (peekxd.mcp_server.middleware).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..core.overlay import GhostOverlayController, OverlayRequest


class OverlayControllerFactory:
    """Callable factory that lazily constructs a GhostOverlayController.

    Pass this to SafetyMiddleware as the ``ghost_overlay`` parameter when
    you want lazy construction instead of a pre-built instance.

    Each call to the factory returns a new GhostOverlayController.
    The middleware calls it once and caches the result.
    """

    def __init__(
        self,
        backend_name: Optional[str] = None,
        timeout: int = 5,
    ) -> None:
        self._backend_name = backend_name
        self._timeout = timeout

    def __call__(self) -> GhostOverlayController:
        """Construct and return a new GhostOverlayController."""
        return GhostOverlayController(
            backend_name=self._backend_name,
            timeout=self._timeout,
        )


def build_ghost_overlay_context(
    request: OverlayRequest,
    elements: Optional[List[Dict[str, Any]]],
) -> OverlayRequest:
    """Enrich an OverlayRequest with snapshot element context.

    This allows the overlay to display which UI elements would be affected
    by the GHOST action, giving the user richer context for their decision.

    Args:
        request: The OverlayRequest to enrich (modified in place).
        elements: List of element dicts from the current snapshot, or None.

    Returns:
        The same OverlayRequest instance with element_context set in preview.
    """
    if elements is not None:
        request.preview["element_context"] = elements
    return request
