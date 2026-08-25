"""Tests for MCP SafetyGuard middleware."""

from unittest.mock import MagicMock

from peekxd.core.audit import AuditLogger
from peekxd.core.zones import RiskDecision, Zone
from peekxd.mcp_server.middleware import (
    MCP_SAFETY_CAPABILITY_VERSION,
    SafetyMiddleware,
)


def test_middleware_enriches_dict_response_with_zone_and_audit_id():
    """Safe MCP actions should be checked, executed, audited, and enriched."""
    guard = MagicMock()
    guard.check_zone.return_value = RiskDecision(
        zone=Zone.DIRECT,
        risk_level="safe",
        reason="Low-risk action with no risk factors",
    )
    logger = AuditLogger(session_id="mcp-test")
    middleware = SafetyMiddleware(safety_guard=guard, audit_logger=logger)

    wrapped = middleware.wrap_tool(
        "move_mouse",
        lambda x, y: {"success": True, "x": x, "y": y},
    )
    result = wrapped(x=10, y=20)

    # G3: the CANONICAL gate decides execution — the legacy guard's check_zone
    # is only a preview/deny signal and can no longer allow an action by itself.
    assert result["success"] is True
    assert result["zone"] == "direct"
    assert result["decision_id"]
    assert result["audit_id"] == "mcp-test:0"
    assert result["safety_capability_version"] == MCP_SAFETY_CAPABILITY_VERSION
    assert logger.actions[0].action == "move_mouse"
    assert logger.actions[0].result["executed"] is True


def test_middleware_wraps_non_dict_response_in_result_envelope():
    """Read-only MCP tools returning lists should still expose safety metadata."""
    guard = MagicMock()
    guard.check_zone.return_value = RiskDecision(zone=Zone.DIRECT, risk_level="safe")
    logger = AuditLogger(session_id="mcp-test")
    middleware = SafetyMiddleware(safety_guard=guard, audit_logger=logger)

    wrapped = middleware.wrap_tool("list_windows", lambda: [{"id": "win1"}])
    result = wrapped()

    assert result["result"] == [{"id": "win1"}]
    assert result["zone"] == "direct"
    assert result["decision_id"]
    assert result["audit_id"] == "mcp-test:0"


def test_middleware_blocks_ghost_zone_without_calling_tool():
    """Dangerous GHOST-zone MCP actions should return a clear blocked error."""
    guard = MagicMock()
    guard.check_zone.return_value = RiskDecision(
        zone=Zone.GHOST,
        risk_level="destructive",
        risk_factors=["destructive_pattern: 'rm '"],
        reason="Risk factors detected: destructive_pattern: 'rm '",
    )
    logger = AuditLogger(session_id="mcp-test")
    tool = MagicMock(return_value={"success": True})
    middleware = SafetyMiddleware(safety_guard=guard, audit_logger=logger)

    wrapped = middleware.wrap_tool("type_text", tool)
    result = wrapped(text="rm -rf /home")

    tool.assert_not_called()
    assert result["success"] is False
    assert result["blocked"] is True
    assert result["zone"] == "ghost"
    assert "Blocked by SafetyDecisionGate" in result["error"]
    assert result["audit_id"] == "mcp-test:0"
    assert logger.actions[0].error == result["error"]
    assert logger.actions[0].result["executed"] is False


def test_check_action_strict_mode_blocks_destructive_pattern():
    """Middleware must call check_action() after check_zone().

    When check_zone() returns a non-GHOST zone (e.g., DIRECT) but check_action()
    raises PermissionDeniedError (STRICT mode destructive detection), the
    middleware must catch the exception and return an MCP error response without
    calling the underlying tool.

    Uses a mock guard where check_zone() passes (DIRECT zone) but check_action()
    raises PermissionDeniedError, proving the middleware calls both safety
    methods independently and handles the check_action() error path.
    """
    from peekxd.core.safety import PermissionDeniedError

    guard = MagicMock()
    guard.check_zone.return_value = RiskDecision(
        zone=Zone.DIRECT,
        risk_level="safe",
        reason="No risk factors — zone allows execution",
    )
    guard.check_action.side_effect = PermissionDeniedError(
        "[PREVIEW BLOCKED] type_text: destructive command detected"
    )
    logger = AuditLogger(session_id="mcp-test")
    tool = MagicMock(return_value={"success": True})
    middleware = SafetyMiddleware(safety_guard=guard, audit_logger=logger)

    wrapped = middleware.wrap_tool("type_text", tool)
    result = wrapped(text="rm -rf /home")

    # G3 ordering: the canonical gate hard-blocks destructive content before
    # the deny-only content screen runs — the tool must never be called.
    guard.check_action.assert_not_called()
    tool.assert_not_called()
    assert result["success"] is False
    assert result["blocked"] is True
    assert "destructive" in result["error"].lower()
