"""Tests for MCP SHADOW response payload stability around capture failures."""

from unittest.mock import MagicMock

from peekxd.core.audit import AuditLogger
from peekxd.core.zones import RiskDecision, Zone
from peekxd.mcp_server.middleware import SafetyMiddleware


def test_shadow_response_keeps_stable_payload_and_warning_when_capture_fails():
    """SHADOW MCP responses should degrade gracefully when screenshot capture fails."""
    guard = MagicMock()
    guard.check_zone.return_value = RiskDecision(zone=Zone.SHADOW, risk_level="safe")
    logger = AuditLogger(session_id="mcp-shadow-failure")
    calls = []

    def failing_capture(path):
        calls.append(path)
        raise RuntimeError("portal denied capture")

    middleware = SafetyMiddleware(
        safety_guard=guard,
        audit_logger=logger,
        capture_fn=failing_capture,
        get_screenshot_path_fn=lambda: "/tmp/peekxd-shadow.png",
    )
    tool = MagicMock(return_value={"success": True, "text": "hello"})

    result = middleware.wrap_tool("type_text", tool)(text="hello")

    tool.assert_called_once_with(text="hello")
    assert calls == ["/tmp/peekxd-shadow.png", "/tmp/peekxd-shadow.png"]
    assert result["success"] is True
    assert result["text"] == "hello"
    assert result["shadow"]["snapshot_before"] is None
    assert result["shadow"]["snapshot_after"] is None
    assert result["shadow"]["changed"] is None
    assert result["shadow"]["diff_summary"] == "No snapshots available for comparison"
    assert "Before snapshot failed: portal denied capture" in result["shadow"]["error"]
    assert "After snapshot failed: portal denied capture" in result["shadow"]["error"]
    assert result["shadow"]["metadata"]["capture_status"] == "degraded"
    assert result["shadow"]["metadata"]["warnings"] == [
        "shadow_screenshot_capture_failed"
    ]
    assert result["zone"] == "shadow"
    assert result["audit_id"]
