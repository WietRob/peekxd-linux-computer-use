"""Tests for peekxd/safety/overlay.py — V4 overlay factory and context builder."""

from peekxd.core.overlay import GhostOverlayController, OverlayRequest
from peekxd.safety.overlay import OverlayControllerFactory, build_ghost_overlay_context


class TestOverlayControllerFactory:
    """AC1: Middleware accepts overlay controller constructor or instance."""

    def test_factory_is_callable(self):
        """Factory is callable and returns a GhostOverlayController when called."""
        factory = OverlayControllerFactory(backend_name="noop", timeout=10)
        controller = factory()
        assert isinstance(controller, GhostOverlayController)
        assert controller.timeout == 10

    def test_factory_lazy_constructor(self):
        """Factory lazy: not constructed until called."""
        factory = OverlayControllerFactory(backend_name="noop")
        # Just creating the factory should NOT create the backend yet
        assert factory._backend_name == "noop"
        # Calling the factory creates the controller with the right backend
        controller = factory()
        assert controller._backend_name == "noop"

    def test_factory_returns_new_instance_each_call(self):
        """Each call to the factory returns a fresh GhostOverlayController."""
        factory = OverlayControllerFactory(backend_name="noop")
        c1 = factory()
        c2 = factory()
        assert c1 is not c2

    def test_factory_default_timeout(self):
        """Default timeout is 5 seconds when not specified."""
        factory = OverlayControllerFactory()
        controller = factory()
        assert controller.timeout == 5


class TestBuildGhostOverlayContext:
    """AC2: overlay.show_preview() receives snapshot element context."""

    def test_context_enriches_request_with_elements(self):
        """build_ghost_overlay_context adds elements to the OverlayRequest."""
        request = OverlayRequest(
            action="click",
            params={"x": 100, "y": 200},
            preview={"risk_factors": ["coordinates"], "reason": "test"},
        )
        elements = [
            {
                "id": "W1-B1",
                "role": "push button",
                "label": "OK",
                "position": (100, 200),
            },
        ]
        enriched = build_ghost_overlay_context(request, elements)
        assert enriched is request  # modifies in place
        assert enriched.preview.get("element_context") == elements

    def test_context_none_elements(self):
        """build_ghost_overlay_context handles None elements gracefully."""
        request = OverlayRequest(
            action="click",
            params={"x": 100, "y": 200},
            preview={"risk_factors": [], "reason": "test"},
        )
        enriched = build_ghost_overlay_context(request, None)
        assert enriched.preview.get("element_context") is None

    def test_context_empty_elements(self):
        """build_ghost_overlay_context handles empty elements list."""
        request = OverlayRequest(
            action="click",
            params={"x": 100, "y": 200},
            preview={},
        )
        enriched = build_ghost_overlay_context(request, [])
        assert enriched.preview.get("element_context") == []
