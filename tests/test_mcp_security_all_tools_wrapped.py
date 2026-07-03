"""Tests that MCP server registrations cannot bypass safety coverage."""

from unittest.mock import patch

from peekxd.config import ConfigManager
from peekxd.mcp_server import create_mcp_server


class CapturingMCP:
    def __init__(self, _name):
        self.registered = []

    def tool(self, *args, **kwargs):
        def capture(func):
            self.registered.append(func)
            return func

        return capture


def test_global_interceptor_wraps_all_bootstrap_registered_tools(monkeypatch, tmp_path):
    """Every bootstrap-registered MCP tool should be registered through one interceptor."""
    monkeypatch.delenv("PEEKXD_SAFETY_MCP", raising=False)
    instances = []

    def factory(name):
        mcp = CapturingMCP(name)
        instances.append(mcp)
        return mcp

    config = ConfigManager(str(tmp_path / "config.json"))
    with patch("peekxd.mcp_server.server.FastMCP", side_effect=factory):
        create_mcp_server(config)

    registered = instances[0].registered
    assert registered
    unwrapped = [func.__name__ for func in registered if not hasattr(func, "__wrapped__")]
    assert unwrapped == []


def test_global_interceptor_keeps_original_tool_names_for_client_discovery(monkeypatch, tmp_path):
    """Safety wrapping must preserve tool names so MCP discovery stays stable."""
    monkeypatch.delenv("PEEKXD_SAFETY_MCP", raising=False)
    instances = []

    def factory(name):
        mcp = CapturingMCP(name)
        instances.append(mcp)
        return mcp

    config = ConfigManager(str(tmp_path / "config.json"))
    with patch("peekxd.mcp_server.server.FastMCP", side_effect=factory):
        create_mcp_server(config)

    tool_names = [func.__name__ for func in instances[0].registered]
    assert "type_text" in tool_names
    assert "peekxd_zone_check" in tool_names
    assert len(tool_names) == len(set(tool_names))
