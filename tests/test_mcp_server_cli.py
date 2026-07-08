"""Tests for MCP CLI safety-control wiring."""

from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from peekxd.cli import cli
from peekxd.config import ConfigManager
from peekxd.core.safety import SafetyLevel
from peekxd.mcp_server import create_mcp_server


class CapturingMCP:
    """Minimal FastMCP stand-in that captures registered tools."""

    def __init__(self, _name, **_kwargs):
        self.tools = {}

    def tool(self, *args, **kwargs):
        def capture(func):
            self.tools[func.__name__] = func
            return func

        return capture


def test_mcp_cli_accepts_safety_overlay_and_audit_export_flags(tmp_path):
    """CLI safety flags should be written into config before server creation."""
    runner = CliRunner()
    mock_server = MagicMock()
    captured = {}
    audit_path = tmp_path / "mcp-audit.json"

    def create_server(config):
        captured["safety_level"] = config.get("mcp.safety_level")
        captured["overlay"] = config.get("mcp.overlay")
        captured["audit_export"] = config.get("mcp.audit_export")
        return mock_server

    with patch("peekxd.mcp_server.create_mcp_server", side_effect=create_server):
        result = runner.invoke(
            cli,
            [
                "mcp",
                "--safety-level",
                "strict",
                "--overlay",
                "noop",
                "--audit-export",
                str(audit_path),
            ],
        )

    assert result.exit_code == 0, result.output
    assert captured == {
        "safety_level": "strict",
        "overlay": "noop",
        "audit_export": str(audit_path),
    }
    mock_server.run.assert_called_once_with(transport="stdio", show_banner=False)


def test_mcp_cli_defaults_do_not_enable_overlay_or_audit_export():
    """Omitting new flags should preserve the existing default MCP behavior."""
    runner = CliRunner()
    mock_server = MagicMock()
    captured = {}

    def create_server(config):
        captured["safety_level"] = config.get("mcp.safety_level", "normal")
        captured["overlay"] = config.get("mcp.overlay")
        captured["audit_export"] = config.get("mcp.audit_export")
        return mock_server

    with patch("peekxd.mcp_server.create_mcp_server", side_effect=create_server):
        result = runner.invoke(cli, ["mcp"])

    assert result.exit_code == 0, result.output
    assert captured == {
        "safety_level": "normal",
        "overlay": None,
        "audit_export": None,
    }


def test_create_mcp_server_passes_configured_safety_controls_to_middleware(tmp_path):
    """Factory config should drive SafetyMiddleware safety level and overlay."""
    config = ConfigManager(str(tmp_path / "config.json"))
    config.set("mcp.safety_level", "strict")
    config.set("mcp.overlay", "noop")
    captured = {}

    def capture_middleware(**kwargs):
        captured.update(kwargs)
        middleware = MagicMock()
        middleware.wrap_tool.side_effect = lambda name, func: func
        middleware.bind_mcp.return_value = None
        return middleware

    with patch("peekxd.mcp_server.server.FastMCP", side_effect=CapturingMCP):
        with patch(
            "peekxd.mcp_server.server.SafetyMiddleware",
            side_effect=capture_middleware,
        ):
            create_mcp_server(config)

    assert captured["safety_guard"].level == SafetyLevel.STRICT
    assert captured["ghost_overlay"] is not None
    assert captured["ghost_overlay"]()._backend_name == "noop"


def test_audit_export_flag_supplies_default_export_path(tmp_path):
    """peekxd_audit_export should use the CLI-configured default path when omitted."""
    config = ConfigManager(str(tmp_path / "config.json"))
    audit_path = tmp_path / "mcp-audit.json"
    config.set("mcp.audit_export", str(audit_path))

    with patch("peekxd.mcp_server.server.FastMCP", side_effect=CapturingMCP):
        server = create_mcp_server(config)

    result = server.tools["peekxd_audit_export"]()

    assert result["success"] is True
    assert result["path"] == str(audit_path)
    assert audit_path.exists()
