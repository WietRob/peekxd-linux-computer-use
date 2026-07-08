"""Tests for MCP safety interceptor runtime guard.

TDD for Cycle 45 D1: mcp-interceptor-runtime-guard.
"""

from unittest.mock import MagicMock

import pytest

from peekxd.core.audit import AuditLogger
from peekxd.core.errors import InterceptorNotActiveError
from peekxd.core.zones import RiskDecision, Zone
from peekxd.mcp_server.middleware import SafetyMiddleware

# ---------------------------------------------------------------------------
# RED phase tests — write before implementation
# ---------------------------------------------------------------------------


class TestAssertInterceptorActive:
    """assert_interceptor_active() guards against interceptor removal."""

    def test_assert_interceptor_active_passes_when_interceptor_is_installed(self):
        """Must not raise when the interceptor is in place."""
        mcp = MagicMock()
        mcp._peekxd_global_safety_interceptor_installed = True
        mcp._peekxd_safety_interceptor_fn = mcp.tool

        middleware = SafetyMiddleware()
        middleware.bind_mcp(mcp)

        # Must not raise
        middleware.assert_interceptor_active()

    def test_assert_interceptor_active_raises_when_interceptor_flag_is_cleared(self):
        """assert_interceptor_active() must raise when the installed flag is False."""
        mcp = MagicMock()
        mcp._peekxd_global_safety_interceptor_installed = False

        middleware = SafetyMiddleware()
        middleware.bind_mcp(mcp)

        with pytest.raises(InterceptorNotActiveError, match="Safety interceptor"):
            middleware.assert_interceptor_active()

    def test_assert_interceptor_active_raises_when_tool_was_replaced(self):
        """assert_interceptor_active() must raise when mcp.tool was replaced."""
        mcp = MagicMock()
        mcp._peekxd_global_safety_interceptor_installed = True
        mcp._peekxd_safety_interceptor_fn = MagicMock()  # the real intercepted fn
        # Simulate: someone replaced mcp.tool with a different function
        mcp.tool = MagicMock()  # different object identity

        middleware = SafetyMiddleware()
        middleware.bind_mcp(mcp)

        with pytest.raises(InterceptorNotActiveError, match="Safety interceptor"):
            middleware.assert_interceptor_active()

    def test_assert_interceptor_active_passes_when_mcp_not_bound(self):
        """Must not raise when no MCP is bound (back-compat)."""
        middleware = SafetyMiddleware()

        # Must not raise — no MCP, no guard to check
        middleware.assert_interceptor_active()


class TestWrapToolInterceptorGuard:
    """wrap_tool must call assert_interceptor_active before dispatching."""

    def test_middleware_wrap_tool_checks_interceptor_before_dispatch(self):
        """wrap_tool must call assert_interceptor_active() before executing."""
        guard = MagicMock()
        guard.check_zone.return_value = RiskDecision(
            zone=Zone.DIRECT,
            risk_level="safe",
            reason="safe",
        )
        guard.check_action.return_value = True
        logger = AuditLogger(session_id="guard-test")

        middleware = SafetyMiddleware(safety_guard=guard, audit_logger=logger)
        middleware.assert_interceptor_active = MagicMock()

        wrapped = middleware.wrap_tool(
            "move_mouse",
            lambda x, y: {"success": True, "x": x, "y": y},
        )
        wrapped(x=10, y=20)

        # The guard must be called BEFORE check_zone
        middleware.assert_interceptor_active.assert_called_once()

    def test_missing_interceptor_returns_structured_mcp_error(self):
        """When the interceptor is missing, the tool must return a structured error."""
        guard = MagicMock()
        guard.check_zone.return_value = RiskDecision(
            zone=Zone.DIRECT,
            risk_level="safe",
            reason="safe",
        )
        guard.check_action.return_value = True
        logger = AuditLogger(session_id="guard-test")

        middleware = SafetyMiddleware(safety_guard=guard, audit_logger=logger)
        # Bind a mock MCP where the interceptor has been removed
        mcp = MagicMock()
        mcp._peekxd_global_safety_interceptor_installed = False
        middleware.bind_mcp(mcp)

        tool = MagicMock(return_value={"success": True})
        wrapped = middleware.wrap_tool("move_mouse", tool)
        result = wrapped(x=10, y=20)

        # Tool must NOT be called
        tool.assert_not_called()
        # The result must be the structured error
        assert result["success"] is False
        assert result["blocked"] is True
        assert "Safety interceptor" in result["error"]

    def test_interceptor_guard_checked_before_zone_and_action_checks(self):
        """The interceptor guard is the FIRST check — before zone and action checks."""
        guard = MagicMock()
        guard.check_zone.return_value = RiskDecision(
            zone=Zone.DIRECT,
            risk_level="safe",
            reason="safe",
        )
        guard.check_action.return_value = True
        logger = AuditLogger(session_id="guard-test")

        middleware = SafetyMiddleware(safety_guard=guard, audit_logger=logger)
        middleware.assert_interceptor_active = MagicMock(
            side_effect=InterceptorNotActiveError("Safety interceptor not active")
        )

        wrapped = middleware.wrap_tool("move_mouse", lambda x, y: {"success": True})
        result = wrapped(x=10, y=20)

        # When the guard fails, zone/action checks must NOT be called
        guard.check_zone.assert_not_called()
        guard.check_action.assert_not_called()
        assert result["success"] is False
        assert result["blocked"] is True
