"""Tests for V4 SafetyMiddleware enhancements — constructor pattern and element context.

AC1: SafetyMiddleware accepts overlay controller constructor or instance.
AC2: APPROVABLE_GHOST actions call overlay.show_preview() with snapshot element context.
"""

from unittest.mock import MagicMock

from peekxd.core.audit import AuditLogger
from peekxd.core.overlay import GhostOverlayController, OverlayDecision
from peekxd.core.zones import RiskDecision, Zone
from peekxd.mcp_server.middleware import SafetyMiddleware
from peekxd.safety.overlay import OverlayControllerFactory

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_guard(risk_factors=None):
    """Create a mock SafetyGuard with empty risk factors (APPROVABLE_GHOST)."""
    guard = MagicMock()
    guard.check_zone.return_value = RiskDecision(
        zone=Zone.GHOST,
        risk_level="warn",
        risk_factors=risk_factors or [],
    )
    return guard


# ===========================================================================
# AC1: SafetyMiddleware accepts overlay controller constructor or instance
# ===========================================================================


class TestOverlayConstructorPattern:
    """SafetyMiddleware must accept either a GhostOverlayController instance
    or a callable (OverlayControllerFactory) that returns one."""

    def test_accepts_instance(self):
        """Middleware accepts a fully constructed GhostOverlayController."""
        overlay = GhostOverlayController(backend_name="noop")
        middleware = SafetyMiddleware(
            safety_guard=_make_guard(),
            audit_logger=AuditLogger(session_id="test"),
            ghost_overlay=overlay,
        )
        assert middleware.ghost_overlay is overlay

    def test_accepts_factory_callable(self):
        """Middleware accepts a callable (factory) and lazy-constructs on first use."""
        factory = OverlayControllerFactory(backend_name="noop")
        middleware = SafetyMiddleware(
            safety_guard=_make_guard(),
            audit_logger=AuditLogger(session_id="test"),
            ghost_overlay=factory,
        )
        # After init, _ghost_overlay_raw stores the factory; lazy construction on access
        controller = middleware._resolve_overlay()
        assert isinstance(controller, GhostOverlayController)
        assert controller._backend_name == "noop"

    def test_factory_is_called_exactly_once(self):
        """When a factory is passed, it is called exactly once (lazy singleton)."""
        call_count = 0

        def counting_factory():
            nonlocal call_count
            call_count += 1
            return GhostOverlayController(backend_name="noop")

        middleware = SafetyMiddleware(
            safety_guard=_make_guard(),
            audit_logger=AuditLogger(session_id="test"),
            ghost_overlay=counting_factory,
        )
        c1 = middleware._resolve_overlay()
        c2 = middleware._resolve_overlay()
        assert c1 is c2
        assert call_count == 1

    def test_approvable_ghost_uses_factory_overlay(self):
        """APPROVABLE_GHOST with factory-configured overlay shows preview."""
        overlay = GhostOverlayController(backend_name="noop")
        call_count = 0

        def counting_factory():
            nonlocal call_count
            call_count += 1
            return overlay

        guard = _make_guard()
        logger = AuditLogger(session_id="test")
        middleware = SafetyMiddleware(
            safety_guard=guard,
            audit_logger=logger,
            ghost_overlay=counting_factory,
        )

        tool = MagicMock(return_value={"success": True})
        wrapped = middleware.wrap_tool("click", tool)
        result = wrapped(x=100, y=200)

        # Factory should have been called once
        assert call_count == 1
        # Result should be blocked (noop overlay returns timeout)
        assert result["success"] is False
        assert result["blocked"] is True


# ===========================================================================
# AC2: APPROVABLE_GHOST actions call overlay.show_preview() with element context
# ===========================================================================


class TestOverlayElementContext:
    """When element context is available, it must be passed to the overlay."""

    def test_element_context_passed_in_overlay_request(self):
        """get_element_context is called and its result added to OverlayRequest."""
        overlay = MagicMock()
        overlay.show_preview.return_value = OverlayDecision(
            approved=False, timed_out=True, backend="noop"
        )
        element_context = [
            {"id": "W1-B1", "role": "push button", "label": "OK"},
        ]
        get_element_context = MagicMock(return_value=element_context)

        middleware = SafetyMiddleware(
            safety_guard=_make_guard(),
            audit_logger=AuditLogger(session_id="test"),
            ghost_overlay=overlay,
            get_element_context=get_element_context,
        )

        tool = MagicMock(return_value={"success": True})
        wrapped = middleware.wrap_tool("click", tool)
        wrapped(x=100, y=200)

        # get_element_context must be called
        get_element_context.assert_called_once()
        # The overlay request must include element_context in preview
        call_args = overlay.show_preview.call_args[0][0]  # OverlayRequest
        assert call_args.preview.get("element_context") == element_context

    def test_no_element_context_when_not_configured(self):
        """When get_element_context is not set, preview has no element_context field."""
        overlay = MagicMock()
        overlay.show_preview.return_value = OverlayDecision(
            approved=False, timed_out=True, backend="noop"
        )

        middleware = SafetyMiddleware(
            safety_guard=_make_guard(),
            audit_logger=AuditLogger(session_id="test"),
            ghost_overlay=overlay,
            # get_element_context NOT set
        )

        tool = MagicMock(return_value={"success": True})
        wrapped = middleware.wrap_tool("click", tool)
        wrapped(x=100, y=200)

        call_args = overlay.show_preview.call_args[0][0]
        # element_context should not be present (or None) when no provider set
        assert "element_context" not in call_args.preview

    def test_element_context_with_approved_overlay(self):
        """Element context is still passed when user approves the action."""
        overlay = MagicMock()
        overlay.show_preview.return_value = OverlayDecision(
            approved=True, backend="tkinter", reason="User approved"
        )
        element_context = [{"id": "W1-T2", "role": "text", "label": "input field"}]
        get_element_context = MagicMock(return_value=element_context)

        middleware = SafetyMiddleware(
            safety_guard=_make_guard(),
            audit_logger=AuditLogger(session_id="test"),
            ghost_overlay=overlay,
            get_element_context=get_element_context,
        )

        tool = MagicMock(return_value={"success": True, "x": 10, "y": 20})
        wrapped = middleware.wrap_tool("type_text", tool)
        result = wrapped(text="hello")

        get_element_context.assert_called_once()
        call_args = overlay.show_preview.call_args[0][0]
        assert call_args.preview.get("element_context") == element_context
        assert result["success"] is True  # approved → executes
