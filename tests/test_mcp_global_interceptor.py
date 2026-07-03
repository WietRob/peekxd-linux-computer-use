"""Tests for the transport-level MCP safety interceptor."""

from unittest.mock import MagicMock, patch

from peekxd.config import ConfigManager
from peekxd.mcp_server import create_mcp_server


class CapturingMCP:
    """Minimal FastMCP stand-in that keeps registered callables executable."""

    def __init__(self, _name):
        self.registered = []

    def tool(self, *args, **kwargs):
        def capture(func):
            self.registered.append(func)
            return func

        return capture


def _create_capturing_server(config):
    instances = []

    def factory(name):
        mcp = CapturingMCP(name)
        instances.append(mcp)
        return mcp

    with patch("peekxd.mcp_server.server.FastMCP", side_effect=factory):
        server = create_mcp_server(config)
    return server


def test_late_registered_mcp_tool_uses_global_safety_interceptor(monkeypatch, tmp_path):
    """Tools registered after bootstrap must still be checked before dispatch."""
    monkeypatch.delenv("PEEKXD_SAFETY_MCP", raising=False)
    config = ConfigManager(str(tmp_path / "config.json"))
    server = _create_capturing_server(config)
    raw_tool = MagicMock(return_value={"success": True})

    def newly_registered_tool(text):
        return raw_tool(text=text)

    registered = server.tool()(newly_registered_tool)
    result = registered(text="rm -rf /tmp/peekxd")

    raw_tool.assert_not_called()
    assert result["success"] is False
    assert result["blocked"] is True
    assert result["zone"] == "ghost"
    assert result["audit_id"]


def test_global_interceptor_respects_trusted_bootstrap_bypass_for_late_tools(
    monkeypatch,
    tmp_path,
):
    """The explicit trusted bootstrap bypass disables the global interceptor uniformly."""
    monkeypatch.setenv("PEEKXD_SAFETY_MCP", "1")
    config = ConfigManager(str(tmp_path / "config.json"))
    config.set("mcp.trusted_bootstrap", True)
    config.set("mcp.transport", "stdio")
    server = _create_capturing_server(config)
    raw_tool = MagicMock(return_value={"success": True, "text": "rm -rf /tmp/peekxd"})

    def newly_registered_tool(text):
        return raw_tool(text=text)

    registered = server.tool()(newly_registered_tool)
    result = registered(text="rm -rf /tmp/peekxd")

    raw_tool.assert_called_once_with(text="rm -rf /tmp/peekxd")
    assert result == {"success": True, "text": "rm -rf /tmp/peekxd"}


def test_global_interceptor_supports_direct_tool_decorator_form(monkeypatch, tmp_path):
    """The interceptor should cover both @mcp.tool and @mcp.tool() styles."""
    monkeypatch.delenv("PEEKXD_SAFETY_MCP", raising=False)
    config = ConfigManager(str(tmp_path / "config.json"))
    server = _create_capturing_server(config)
    raw_tool = MagicMock(return_value={"success": True})

    def direct_decorator_tool(text):
        return raw_tool(text=text)

    registered = server.tool(direct_decorator_tool)
    result = registered(text="rm -rf /tmp/peekxd")

    raw_tool.assert_not_called()
    assert result["success"] is False
    assert result["blocked"] is True
    assert result["zone"] == "ghost"
