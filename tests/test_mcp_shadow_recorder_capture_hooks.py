"""Tests for MCP shadow recorder screenshot capture hooks."""

import stat
from pathlib import Path
from unittest.mock import MagicMock, patch

from peekxd.config import ConfigManager
from peekxd.core.audit import AuditLogger
from peekxd.core.zones import RiskDecision, Zone
from peekxd.mcp_server.middleware import SafetyMiddleware
from peekxd.mcp_server.server import _create_shadow_recorder


def test_shadow_middleware_uses_capture_callbacks_for_before_and_after(tmp_path):
    """SHADOW MCP actions should capture before and after snapshots when callbacks succeed."""
    paths = [tmp_path / "before.png", tmp_path / "after.png"]
    captured = []

    def next_path():
        return str(paths[len(captured)])

    def capture(path):
        captured.append(path)
        with open(path, "wb") as handle:
            handle.write(f"image-{len(captured)}".encode())

    guard = MagicMock()
    guard.check_zone.return_value = RiskDecision(zone=Zone.SHADOW, risk_level="safe")
    logger = AuditLogger(session_id="mcp-shadow-capture")
    middleware = SafetyMiddleware(
        safety_guard=guard,
        audit_logger=logger,
        capture_fn=capture,
        get_screenshot_path_fn=next_path,
    )
    tool = MagicMock(return_value={"success": True})

    result = middleware.wrap_tool("click", tool)(x=10, y=20)

    tool.assert_called_once_with(x=10, y=20)
    assert captured == [str(paths[0]), str(paths[1])]
    assert result["shadow"]["snapshot_before"]["screenshot_path"] == str(paths[0])
    assert result["shadow"]["snapshot_after"]["screenshot_path"] == str(paths[1])
    assert result["shadow"]["changed"] is True
    assert result["shadow"]["error"] is None
    assert result["shadow"]["metadata"]["capture_status"] == "captured"


def test_mcp_server_shadow_recorder_uses_configured_screenshot_provider(tmp_path):
    """Server shadow recorder should expose capture callbacks backed by screenshot provider."""
    config = ConfigManager(str(tmp_path / "config.json"))
    provider = MagicMock()

    with patch("peekxd.mcp_server.server.get_screenshot_provider", return_value=provider):
        recorder = _create_shadow_recorder(config)
        path = recorder._get_path()
        recorder._capture(path)

    assert path.startswith(str(tmp_path / "mcp-shadow"))
    assert path.endswith(".png")
    provider.capture_screen.assert_called_once_with(path)


def test_mcp_shadow_capture_artifacts_are_owner_private(tmp_path):
    """Shadow capture directory and screenshot files should be owner-private."""
    config = ConfigManager(str(tmp_path / "config.json"))
    provider = MagicMock()

    def write_capture(path):
        Path(path).write_bytes(b"sensitive screen pixels")

    provider.capture_screen.side_effect = write_capture

    with patch("peekxd.mcp_server.server.get_screenshot_provider", return_value=provider):
        recorder = _create_shadow_recorder(config)
        path = recorder._get_path()
        recorder._capture(path)

    capture_dir = Path(path).parent
    assert stat.S_IMODE(capture_dir.stat().st_mode) == 0o700
    assert stat.S_IMODE(Path(path).stat().st_mode) == 0o600
