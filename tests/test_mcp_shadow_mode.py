"""Tests for MCP SHADOW-zone execution through ShadowRecorder."""

from unittest.mock import MagicMock

from peekxd.core.audit import AuditLogger
from peekxd.core.shadow import ShadowResult, ShadowSnapshot
from peekxd.core.zones import RiskDecision, Zone
from peekxd.mcp_server.middleware import SafetyMiddleware


class RecordingShadowRecorder:
    """Test double that proves MCP execution is routed through ShadowRecorder."""

    def __init__(self):
        self.calls = []

    def wrap(self, action_callable, action, params, screen_state=None):
        self.calls.append(
            {
                "action": action,
                "params": params,
                "screen_state": screen_state,
            }
        )
        result = action_callable()
        return result, ShadowResult(
            before_snapshot=ShadowSnapshot(
                timestamp="1.0",
                screenshot_path="/tmp/mcp-before.png",
                metadata={"source": "test"},
            ),
            after_snapshot=ShadowSnapshot(
                timestamp="2.0",
                screenshot_path="/tmp/mcp-after.png",
                metadata={"source": "test"},
            ),
            changed=True,
            diff_summary="Screen changed: files differ",
        )


def test_shadow_zone_tool_executes_through_shadow_recorder():
    """SHADOW MCP actions should be wrapped with before/after shadow snapshots."""
    guard = MagicMock()
    guard.check_zone.return_value = RiskDecision(zone=Zone.SHADOW, risk_level="safe")
    logger = AuditLogger(session_id="mcp-shadow")
    recorder = RecordingShadowRecorder()
    tool = MagicMock(return_value={"success": True, "x": 10, "y": 20})
    middleware = SafetyMiddleware(
        safety_guard=guard,
        audit_logger=logger,
        shadow_recorder=recorder,
    )

    wrapped = middleware.wrap_tool("click", tool)
    result = wrapped(x=10, y=20)

    tool.assert_called_once_with(x=10, y=20)
    assert recorder.calls == [
        {
            "action": "click",
            "params": {"x": 10, "y": 20},
            "screen_state": None,
        }
    ]
    assert result["success"] is True
    assert result["zone"] == "shadow"
    assert result["shadow"]["snapshot_before"]["screenshot_path"] == "/tmp/mcp-before.png"
    assert result["shadow"]["snapshot_after"]["screenshot_path"] == "/tmp/mcp-after.png"
    assert logger.actions[0].result["shadow"]["changed"] is True
    assert logger.actions[0].result["executed"] is True


def test_direct_zone_tool_does_not_use_shadow_recorder():
    """Non-SHADOW MCP actions should keep the existing direct execution path."""
    guard = MagicMock()
    guard.check_zone.return_value = RiskDecision(zone=Zone.DIRECT, risk_level="safe")
    logger = AuditLogger(session_id="mcp-shadow")
    recorder = RecordingShadowRecorder()
    tool = MagicMock(return_value={"success": True})
    middleware = SafetyMiddleware(
        safety_guard=guard,
        audit_logger=logger,
        shadow_recorder=recorder,
    )

    result = middleware.wrap_tool("move_mouse", tool)(x=10, y=20)

    tool.assert_called_once_with(x=10, y=20)
    assert recorder.calls == []
    assert result["success"] is True
    assert result["zone"] == "direct"
    assert "shadow" not in result
