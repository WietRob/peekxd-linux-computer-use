"""Tests for MCP dispatch-time safety guard."""

import asyncio
from unittest.mock import MagicMock, patch

from peekxd.config import ConfigManager
from peekxd.mcp_server import create_mcp_server


class DispatchingMCP:
    """Minimal FastMCP stand-in with a mutable dispatch registry."""

    def __init__(self, _name):
        self._tools = {}

    def tool(self, *args, **kwargs):
        def capture(func):
            self._tools[func.__name__] = func
            return func

        return capture

    async def call_tool(self, name, arguments=None, **kwargs):
        arguments = arguments or {}
        return self._tools[name](**arguments)


def _create_dispatching_server(config):
    instances = []

    def factory(name):
        mcp = DispatchingMCP(name)
        instances.append(mcp)
        return mcp

    with patch("peekxd.mcp_server.server.FastMCP", side_effect=factory):
        server = create_mcp_server(config)
    return server


def _structured_result(result):
    return getattr(result, "structured_content", result)


def test_dispatch_guard_blocks_tool_registry_mutation_bypass(monkeypatch, tmp_path):
    """Raw tools injected directly into the dispatch registry must still be guarded."""
    monkeypatch.delenv("PEEKXD_SAFETY_MCP", raising=False)
    config = ConfigManager(str(tmp_path / "config.json"))
    server = _create_dispatching_server(config)
    raw_tool = MagicMock(return_value={"success": True})
    server._tools["type_text"] = raw_tool

    result = asyncio.run(
        server.call_tool("type_text", {"text": "rm -rf /tmp/peekxd"})
    )
    payload = _structured_result(result)

    raw_tool.assert_not_called()
    assert payload["success"] is False
    assert payload["blocked"] is True
    assert payload["zone"] == "ghost"
    assert payload["audit_id"]


def test_dispatch_guard_allows_safe_registry_mutation_with_audit(monkeypatch, tmp_path):
    """Direct registry mutation is allowed only after dispatch-time safety checks."""
    monkeypatch.delenv("PEEKXD_SAFETY_MCP", raising=False)
    config = ConfigManager(str(tmp_path / "config.json"))
    server = _create_dispatching_server(config)
    raw_tool = MagicMock(return_value={"success": True, "x": 10, "y": 20})
    server._tools["move_mouse"] = raw_tool

    result = asyncio.run(server.call_tool("move_mouse", {"x": 10, "y": 20}))
    payload = _structured_result(result)

    raw_tool.assert_called_once_with(x=10, y=20)
    assert payload["success"] is True
    assert payload["zone"] == "direct"
    assert payload["audit_id"]


def test_dispatch_guard_respects_trusted_bootstrap_bypass(monkeypatch, tmp_path):
    """The explicit trusted bootstrap bypass disables dispatch-time enforcement."""
    monkeypatch.setenv("PEEKXD_SAFETY_MCP", "1")
    config = ConfigManager(str(tmp_path / "config.json"))
    config.set("mcp.trusted_bootstrap", True)
    config.set("mcp.transport", "stdio")
    server = _create_dispatching_server(config)
    raw_tool = MagicMock(return_value={"success": True, "text": "rm -rf /tmp/peekxd"})
    server._tools["type_text"] = raw_tool

    result = asyncio.run(
        server.call_tool("type_text", {"text": "rm -rf /tmp/peekxd"})
    )

    raw_tool.assert_called_once_with(text="rm -rf /tmp/peekxd")
    assert result == {"success": True, "text": "rm -rf /tmp/peekxd"}
