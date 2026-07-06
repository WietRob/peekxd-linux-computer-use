"""Tests for peekxd_safety_status MCP tool."""

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


def test_safety_status_returns_policy_with_env_absent(monkeypatch, tmp_path):
    """peekxd_safety_status returns resolved policy when env is absent."""
    monkeypatch.delenv("PEEKXD_SAFETY_MCP", raising=False)
    config = ConfigManager(str(tmp_path / "config.json"))
    config.set("mcp.trusted_bootstrap", False)

    tools = _collect_tools(config)
    result = tools["peekxd_safety_status"]()

    assert result["safety_bypass_enabled"] is False
    assert result["safety_bypass_source"] == "default_disabled"
    assert result["safety_bypass_env_state"] == "absent"
    assert result["trusted_bootstrap"] is False
    assert result["transport"] == "stdio"
    assert result["host"] == "localhost"


def test_safety_status_returns_policy_with_allowlist_env(monkeypatch, tmp_path):
    """peekxd_safety_status returns resolved policy when env is allowlisted."""
    monkeypatch.setenv("PEEKXD_SAFETY_MCP", "1")
    config = ConfigManager(str(tmp_path / "config.json"))
    config.set("mcp.trusted_bootstrap", True)
    config.set("mcp.transport", "stdio")

    tools = _collect_tools(config)
    result = tools["peekxd_safety_status"]()

    assert result["safety_bypass_enabled"] is True
    assert result["safety_bypass_source"] == "env:PEEKXD_SAFETY_MCP=1"
    assert result["safety_bypass_env_state"] == "allowlisted"
    assert result["trusted_bootstrap"] is True
    assert result["transport"] == "stdio"
    assert result["host"] == "localhost"


def test_safety_status_returns_policy_with_non_allowlisted_env(monkeypatch, tmp_path):
    """peekxd_safety_status returns resolved policy when env is not allowlisted."""
    monkeypatch.setenv("PEEKXD_SAFETY_MCP", "0")
    config = ConfigManager(str(tmp_path / "config.json"))
    config.set("mcp.trusted_bootstrap", True)

    tools = _collect_tools(config)
    result = tools["peekxd_safety_status"]()

    assert result["safety_bypass_enabled"] is False
    assert result["safety_bypass_source"] == "env:PEEKXD_SAFETY_MCP:not_allowlisted"
    assert result["safety_bypass_env_state"] == "not_allowlisted"
    assert result["trusted_bootstrap"] is True


def test_safety_status_returns_policy_with_trusted_bootstrap_false(
    monkeypatch, tmp_path
):
    """peekxd_safety_status shows source when env=1 but trusted_bootstrap=false."""
    monkeypatch.setenv("PEEKXD_SAFETY_MCP", "1")
    config = ConfigManager(str(tmp_path / "config.json"))
    config.set("mcp.trusted_bootstrap", False)
    config.set("mcp.transport", "stdio")

    tools = _collect_tools(config)
    result = tools["peekxd_safety_status"]()

    assert result["safety_bypass_enabled"] is False
    assert result["safety_bypass_source"] == (
        "env:PEEKXD_SAFETY_MCP=1;trusted_bootstrap=false"
    )
    assert result["safety_bypass_env_state"] == "allowlisted"
    assert result["trusted_bootstrap"] is False


def test_safety_status_tool_is_registered():
    """peekxd_safety_status tool is registered on the MCP server."""
    config = ConfigManager()
    tools = _collect_tools(config)
    assert "peekxd_safety_status" in tools, (
        f"peekxd_safety_status not found in registered tools: {list(tools.keys())}"
    )
