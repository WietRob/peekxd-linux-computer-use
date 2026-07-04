"""Tests for D1: mcp-ghost-overlay-gateway.

Validates that SafetyMiddleware.wrap_tool() routes APPROVABLE_GHOST
actions through GhostOverlayController.show_preview() before blocking,
and that HARD_BLOCKED_GHOST short-circuits without overlay.
"""

from unittest.mock import MagicMock

from peekxd.core.audit import AuditLogger
from peekxd.core.overlay import OverlayDecision
from peekxd.core.zones import RiskDecision, Zone
from peekxd.mcp_server.middleware import SafetyMiddleware

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_middleware(
    *,
    check_zone_return=None,
    overlay_decision=None,
):
    """Create a SafetyMiddleware with mocked safety_guard and ghost_overlay."""
    guard = MagicMock()
    guard.check_zone.return_value = check_zone_return or RiskDecision(
        zone=Zone.GHOST,
        risk_level="warn",
        risk_factors=[],
    )
    overlay = MagicMock()
    if overlay_decision is not None:
        overlay.show_preview.return_value = overlay_decision
    else:
        overlay.show_preview.return_value = OverlayDecision(
            approved=False, backend="noop",
        )
    return SafetyMiddleware(
        safety_guard=guard,
        audit_logger=AuditLogger(session_id="test"),
        ghost_overlay=overlay,
    )


# ===========================================================================
# Test 1: HARD_BLOCKED_GHOST short-circuits — no overlay shown
# ===========================================================================

def test_hard_blocked_ghost_short_circuits_without_overlay():
    """HARD_BLOCKED_GHOST actions must NOT invoke overlay — short-circuit to blocked."""
    guard = MagicMock()
    guard.check_zone.return_value = RiskDecision(
        zone=Zone.GHOST,
        risk_level="destructive",
        risk_factors=["destructive_pattern: 'rm '"],
        reason="Risk factors: destructive_pattern: 'rm '",
    )
    overlay = MagicMock()
    logger = AuditLogger(session_id="test")
    middleware = SafetyMiddleware(
        safety_guard=guard,
        audit_logger=logger,
        ghost_overlay=overlay,
    )

    tool = MagicMock(return_value={"success": True})
    wrapped = middleware.wrap_tool("type_text", tool)
    result = wrapped(text="rm -rf /home")

    # Overlay MUST NOT be called for HARD_BLOCKED
    overlay.show_preview.assert_not_called()
    # Tool MUST NOT execute
    tool.assert_not_called()
    # Response MUST be blocked
    assert result["success"] is False
    assert result["blocked"] is True
    assert result["zone"] == "ghost"
    assert "Blocked by SafetyGuard" in result["error"]


# ===========================================================================
# Test 2: APPROVABLE_GHOST with denied overlay → blocked response
# ===========================================================================

def test_approvable_ghost_shows_overlay_before_blocking():
    """APPROVABLE_GHOST must show overlay; denied => blocked with classification."""
    guard = MagicMock()
    guard.check_zone.return_value = RiskDecision(
        zone=Zone.GHOST,
        risk_level="warn",
        risk_factors=[],  # No risk factors → APPROVABLE for known safe actions
    )
    overlay = MagicMock()
    overlay.show_preview.return_value = OverlayDecision(
        approved=False, cancelled=True, backend="tkinter", reason="User cancelled"
    )
    logger = AuditLogger(session_id="test")
    middleware = SafetyMiddleware(
        safety_guard=guard,
        audit_logger=logger,
        ghost_overlay=overlay,
    )

    tool = MagicMock(return_value={"success": True})
    wrapped = middleware.wrap_tool("click", tool)
    result = wrapped(x=100, y=200)

    # Overlay MUST be called
    overlay.show_preview.assert_called_once()
    # Tool MUST NOT execute (user denied)
    tool.assert_not_called()
    # Response MUST be blocked
    assert result["success"] is False
    assert result["blocked"] is True
    assert result["zone"] == "ghost"


# ===========================================================================
# Test 3: APPROVABLE_GHOST with approved overlay → execution proceeds
# ===========================================================================

def test_approvable_ghost_overlay_approved_proceeds():
    """APPROVABLE_GHOST with approved overlay must execute the MCP tool."""
    guard = MagicMock()
    guard.check_zone.return_value = RiskDecision(
        zone=Zone.GHOST,
        risk_level="warn",
        risk_factors=[],
    )
    overlay = MagicMock()
    overlay.show_preview.return_value = OverlayDecision(
        approved=True, backend="tkinter", reason="User approved"
    )
    logger = AuditLogger(session_id="test")
    middleware = SafetyMiddleware(
        safety_guard=guard,
        audit_logger=logger,
        ghost_overlay=overlay,
    )

    tool = MagicMock(return_value={"success": True, "x": 100, "y": 200})
    wrapped = middleware.wrap_tool("click", tool)
    result = wrapped(x=100, y=200)

    # Overlay MUST be called
    overlay.show_preview.assert_called_once()
    # Tool MUST execute
    tool.assert_called_once()
    # Result reflects execution
    assert result["success"] is True


# ===========================================================================
# Test 4: APPROVABLE_GHOST with timeout → blocked response
# ===========================================================================

def test_approvable_ghost_overlay_timeout_blocks():
    """APPROVABLE_GHOST with overlay timeout must return blocked response."""
    guard = MagicMock()
    guard.check_zone.return_value = RiskDecision(
        zone=Zone.GHOST,
        risk_level="warn",
        risk_factors=[],
    )
    overlay = MagicMock()
    overlay.show_preview.return_value = OverlayDecision(
        approved=False, timed_out=True, backend="noop", reason="Timed out after 5s"
    )
    logger = AuditLogger(session_id="test")
    middleware = SafetyMiddleware(
        safety_guard=guard,
        audit_logger=logger,
        ghost_overlay=overlay,
    )

    tool = MagicMock(return_value={"success": True})
    wrapped = middleware.wrap_tool("click", tool)
    result = wrapped(x=50, y=50)

    overlay.show_preview.assert_called_once()
    tool.assert_not_called()
    assert result["success"] is False
    assert result["blocked"] is True


# ===========================================================================
# Test 5: approved GHOST action audit log includes approval_source
# ===========================================================================

def test_approved_ghost_audit_includes_approval_source():
    """Audit log for approved GHOST actions must include approval_source=overlay."""
    guard = MagicMock()
    guard.check_zone.return_value = RiskDecision(
        zone=Zone.GHOST,
        risk_level="warn",
        risk_factors=[],
    )
    overlay = MagicMock()
    overlay.show_preview.return_value = OverlayDecision(
        approved=True, backend="tkinter", reason="User approved"
    )
    logger = AuditLogger(session_id="test")
    middleware = SafetyMiddleware(
        safety_guard=guard,
        audit_logger=logger,
        ghost_overlay=overlay,
    )

    wrapped = middleware.wrap_tool(
        "click",
        lambda x, y: {"success": True, "clicked": True},
    )
    wrapped(x=10, y=20)

    # Find the audit entry for this action
    assert len(logger.actions) > 0
    entry = logger.actions[0]
    assert entry.action == "click"
    assert entry.result.get("executed") is True
    # approval_source must be set
    assert entry.result.get("approval_source") == "overlay"


# ===========================================================================
# Test 6: Middleware created without ghost_overlay falls back safely
# ===========================================================================

def test_middleware_without_ghost_overlay_still_blocks_all_ghost():
    """When no ghost_overlay set, ALL GHOST actions blocked (backward compat)."""
    guard = MagicMock()
    guard.check_zone.return_value = RiskDecision(
        zone=Zone.GHOST,
        risk_level="warn",
        risk_factors=[],
    )
    logger = AuditLogger(session_id="test")
    middleware = SafetyMiddleware(safety_guard=guard, audit_logger=logger)

    tool = MagicMock(return_value={"success": True})
    wrapped = middleware.wrap_tool("click", tool)
    result = wrapped(x=100, y=200)

    # Without overlay controller, everything is blocked
    tool.assert_not_called()
    assert result["success"] is False
    assert result["blocked"] is True
