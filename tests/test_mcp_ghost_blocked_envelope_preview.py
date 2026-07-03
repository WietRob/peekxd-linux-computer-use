"""Tests for structured GHOST preview envelopes in MCP blocked responses."""

from unittest.mock import MagicMock

from peekxd.core.audit import AuditLogger
from peekxd.core.zones import RiskDecision, Zone, ZoneDecision
from peekxd.mcp_server.middleware import SafetyMiddleware


def test_ghost_blocked_mcp_response_includes_structured_preview_envelope():
    """GHOST-blocked tools should return preview metadata without executing."""
    params = {"text": "rm -rf /tmp/peekxd"}
    decision = RiskDecision(
        zone=Zone.GHOST,
        risk_level="destructive",
        risk_factors=["destructive_pattern: 'rm '"],
        reason="Risk factors detected: destructive_pattern: 'rm '",
    )
    guard = MagicMock()
    guard.check_zone.return_value = decision
    logger = AuditLogger(session_id="mcp-ghost-envelope")
    middleware = SafetyMiddleware(safety_guard=guard, audit_logger=logger)
    raw_tool = MagicMock(return_value={"success": True})

    result = middleware.wrap_tool("type_text", raw_tool)(**params)

    raw_tool.assert_not_called()
    assert result["success"] is False
    assert result["blocked"] is True
    assert result["error"].startswith("Blocked by SafetyGuard")
    assert result["zone"] == "ghost"
    assert result["ghost_preview"] == ZoneDecision.create_ghost_preview(
        "type_text",
        params,
        decision,
    ).to_dict()
    assert result["ghost_preview"]["risk_factors"] == decision.risk_factors
    assert result["ghost_preview"]["text_preview"] == params["text"]
    assert result["ghost_preview"]["markup_path"] is None
    assert result["ghost_preview"]["required_confirmation"] is True
    assert result["audit_id"]


def test_direct_blocked_response_shape_omits_ghost_preview_for_non_ghost_zones():
    """NORMAL/STRICT non-GHOST blocked responses keep the current wire format."""
    decision = RiskDecision(
        zone=Zone.GUIDED,
        risk_level="warn",
        risk_factors=["manual_policy_block"],
        reason="Operator policy blocked the action",
    )
    middleware = SafetyMiddleware(audit_logger=AuditLogger(session_id="mcp-guided-block"))

    result = middleware._blocked_response("click", {"x": 1, "y": 2}, decision)

    assert result["success"] is False
    assert result["blocked"] is True
    assert result["risk_factors"] == ["manual_policy_block"]
    assert result["zone"] == "guided"
    assert "ghost_preview" not in result
