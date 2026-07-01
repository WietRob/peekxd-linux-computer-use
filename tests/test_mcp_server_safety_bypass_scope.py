"""Tests for MCP safety bypass scoping."""

import logging
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


def test_env_safety_bypass_does_not_disable_middleware_without_trusted_bootstrap(
    monkeypatch,
    tmp_path,
):
    """PEEKXD_SAFETY_MCP=0 alone must not globally bypass MCP SafetyMiddleware."""
    monkeypatch.setenv("PEEKXD_SAFETY_MCP", "0")
    config = ConfigManager(str(tmp_path / "config.json"))
    provider = MagicMock()

    with patch("peekxd.mcp_server.server._get_input", return_value=provider):
        tools = _collect_tools(config)
        result = tools["type_text"](text="rm -rf /tmp/peekxd")

    provider.type_text.assert_not_called()
    assert result["success"] is False
    assert result["blocked"] is True
    assert result["zone"] == "ghost"
    assert result["audit_id"]


def test_trusted_local_bootstrap_bypass_requires_explicit_config_and_warns(
    monkeypatch,
    tmp_path,
    caplog,
):
    """Only an explicit trusted local bootstrap context may activate bypass mode."""
    monkeypatch.setenv("PEEKXD_SAFETY_MCP", "0")
    config = ConfigManager(str(tmp_path / "config.json"))
    config.set("mcp.trusted_bootstrap", True)
    config.set("mcp.transport", "stdio")
    provider = MagicMock()

    with caplog.at_level(logging.WARNING, logger="peekxd.mcp_server.server"):
        with patch("peekxd.mcp_server.server._get_input", return_value=provider):
            tools = _collect_tools(config)
            result = tools["type_text"](text="rm -rf /tmp/peekxd")

    provider.type_text.assert_called_once_with("rm -rf /tmp/peekxd")
    assert result == {"success": True, "text": "rm -rf /tmp/peekxd"}
    assert "Trusted local MCP bootstrap safety bypass is active" in caplog.text


def test_trusted_bootstrap_bypass_rejects_nonlocal_sse_transport(monkeypatch, tmp_path):
    """Explicit trust is insufficient when the configured MCP transport is remote SSE."""
    monkeypatch.setenv("PEEKXD_SAFETY_MCP", "0")
    config = ConfigManager(str(tmp_path / "config.json"))
    config.set("mcp.trusted_bootstrap", True)
    config.set("mcp.transport", "sse")
    config.set("mcp.host", "0.0.0.0")
    provider = MagicMock()

    with patch("peekxd.mcp_server.server._get_input", return_value=provider):
        tools = _collect_tools(config)
        result = tools["type_text"](text="rm -rf /tmp/peekxd")

    provider.type_text.assert_not_called()
    assert result["success"] is False
    assert result["blocked"] is True
    assert result["zone"] == "ghost"
