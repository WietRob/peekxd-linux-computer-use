"""Tests for explicit MCP safety bypass allowlist policy."""

from unittest.mock import MagicMock, patch

from peekxd.config import ConfigManager
from peekxd.mcp_server import create_mcp_server


def _collect_tools(config):
    registered = []

    def capture_tool(func):
        registered.append(func)
        return func

    mock_mcp = MagicMock()
    mock_mcp.tool = MagicMock(return_value=capture_tool)
    with patch("peekxd.mcp_server.server.FastMCP", return_value=mock_mcp):
        create_mcp_server(config)
    return {func.__name__: func for func in registered}


def test_safety_bypass_disabled_without_explicit_allowlist_env(monkeypatch, tmp_path):
    """Trusted bootstrap config alone must not bypass MCP SafetyMiddleware."""
    monkeypatch.delenv("PEEKXD_SAFETY_MCP", raising=False)
    config = ConfigManager(str(tmp_path / "config.json"))
    config.set("mcp.trusted_bootstrap", True)
    config.set("mcp.transport", "stdio")
    provider = MagicMock()

    with patch("peekxd.mcp_server.server._get_input", return_value=provider):
        tools = _collect_tools(config)
        result = tools["type_text"](text="rm -rf /tmp/peekxd")

    provider.type_text.assert_not_called()
    assert result["success"] is False
    assert result["blocked"] is True
    assert result["zone"] == "ghost"
    assert result["audit_id"]


def test_safety_bypass_requires_allowlist_env_value_one(monkeypatch, tmp_path):
    """PEEKXD_SAFETY_MCP=1 is the explicit allowlist value for legacy bypass."""
    monkeypatch.setenv("PEEKXD_SAFETY_MCP", "1")
    config = ConfigManager(str(tmp_path / "config.json"))
    config.set("mcp.trusted_bootstrap", True)
    config.set("mcp.transport", "stdio")
    provider = MagicMock()

    with patch("peekxd.mcp_server.server._get_input", return_value=provider):
        tools = _collect_tools(config)
        result = tools["type_text"](text="rm -rf /tmp/peekxd")

    provider.type_text.assert_called_once_with("rm -rf /tmp/peekxd")
    assert result == {"success": True, "text": "rm -rf /tmp/peekxd"}


def test_safety_bypass_rejects_legacy_zero_value(monkeypatch, tmp_path):
    """Legacy PEEKXD_SAFETY_MCP=0 must no longer enable bypass accidentally."""
    monkeypatch.setenv("PEEKXD_SAFETY_MCP", "0")
    config = ConfigManager(str(tmp_path / "config.json"))
    config.set("mcp.trusted_bootstrap", True)
    config.set("mcp.transport", "stdio")
    provider = MagicMock()

    with patch("peekxd.mcp_server.server._get_input", return_value=provider):
        tools = _collect_tools(config)
        result = tools["type_text"](text="rm -rf /tmp/peekxd")

    provider.type_text.assert_not_called()
    assert result["success"] is False
    assert result["blocked"] is True
    assert result["zone"] == "ghost"
