"""Tests for MCP startup safety policy evidence."""

import logging
from unittest.mock import MagicMock, patch

from peekxd.config import ConfigManager
from peekxd.mcp_server import create_mcp_server


def _create_with_mocks(config, audit_logger):
    mock_mcp = MagicMock()
    mock_mcp.tool = MagicMock(return_value=lambda func: func)
    with patch("peekxd.mcp_server.server.FastMCP", return_value=mock_mcp):
        with patch("peekxd.mcp_server.server.get_logger", return_value=audit_logger):
            create_mcp_server(config)


def test_mcp_startup_records_disabled_policy_evidence(monkeypatch, tmp_path, caplog):
    """MCP startup records resolved bypass state and source when bypass is disabled."""
    monkeypatch.delenv("PEEKXD_SAFETY_MCP", raising=False)
    config = ConfigManager(str(tmp_path / "config.json"))
    config.set("mcp.trusted_bootstrap", False)
    audit_logger = MagicMock()

    with caplog.at_level(logging.INFO, logger="peekxd.mcp_server.server"):
        _create_with_mocks(config, audit_logger)

    audit_logger.log_action.assert_any_call(
        "mcp_startup_policy",
        {
            "safety_bypass_enabled": False,
            "safety_bypass_source": "default_disabled",
            "safety_bypass_env": None,
            "trusted_bootstrap": False,
            "transport": "stdio",
            "host": "localhost",
        },
        {"success": True},
    )
    assert "MCP startup policy evidence" in caplog.text
    assert "safety_bypass_enabled=False" in caplog.text
    assert "safety_bypass_source=default_disabled" in caplog.text


def test_mcp_startup_records_allowlist_env_policy_evidence(monkeypatch, tmp_path, caplog):
    """MCP startup records resolved bypass state and allowlist env source."""
    monkeypatch.setenv("PEEKXD_SAFETY_MCP", "1")
    config = ConfigManager(str(tmp_path / "config.json"))
    config.set("mcp.trusted_bootstrap", True)
    config.set("mcp.transport", "stdio")
    audit_logger = MagicMock()

    with caplog.at_level(logging.INFO, logger="peekxd.mcp_server.server"):
        _create_with_mocks(config, audit_logger)

    audit_logger.log_action.assert_any_call(
        "mcp_startup_policy",
        {
            "safety_bypass_enabled": True,
            "safety_bypass_source": "env:PEEKXD_SAFETY_MCP=1",
            "safety_bypass_env": "1",
            "trusted_bootstrap": True,
            "transport": "stdio",
            "host": "localhost",
        },
        {"success": True},
    )
    assert "MCP startup policy evidence" in caplog.text
    assert "safety_bypass_enabled=True" in caplog.text
    assert "safety_bypass_source=env:PEEKXD_SAFETY_MCP=1" in caplog.text
