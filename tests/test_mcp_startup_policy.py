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
            "safety_bypass_env_state": "absent",
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
            "safety_bypass_env_state": "allowlisted",
            "trusted_bootstrap": True,
            "transport": "stdio",
            "host": "localhost",
        },
        {"success": True},
    )
    assert "MCP startup policy evidence" in caplog.text
    assert "safety_bypass_enabled=True" in caplog.text
    assert "safety_bypass_source=env:PEEKXD_SAFETY_MCP=1" in caplog.text


def test_mcp_startup_redacts_non_allowlisted_env_values(monkeypatch, tmp_path, caplog):
    """Startup evidence must not log or audit raw non-allowlisted env values."""
    monkeypatch.setenv("PEEKXD_SAFETY_MCP", "operator-note-do-not-log")
    config = ConfigManager(str(tmp_path / "config.json"))
    audit_logger = MagicMock()

    with caplog.at_level(logging.INFO, logger="peekxd.mcp_server.server"):
        _create_with_mocks(config, audit_logger)

    _action, policy, _result = audit_logger.log_action.call_args.args
    assert policy["safety_bypass_enabled"] is False
    assert policy["safety_bypass_source"] == "env:PEEKXD_SAFETY_MCP:not_allowlisted"
    assert policy["safety_bypass_env_state"] == "not_allowlisted"
    assert "operator-note-do-not-log" not in caplog.text
    assert "operator-note-do-not-log" not in str(audit_logger.log_action.call_args)


def test_mcp_startup_rejects_empty_host_for_non_stdio_transport(monkeypatch, tmp_path):
    """An empty non-stdio host must not count as trusted local bootstrap."""
    monkeypatch.setenv("PEEKXD_SAFETY_MCP", "1")
    config = ConfigManager(str(tmp_path / "config.json"))
    config.set("mcp.trusted_bootstrap", True)
    config.set("mcp.transport", "sse")
    config.set("mcp.host", "")
    audit_logger = MagicMock()

    _create_with_mocks(config, audit_logger)

    _action, policy, _result = audit_logger.log_action.call_args.args
    assert policy["safety_bypass_enabled"] is False
    assert policy["trusted_bootstrap"] is False
    assert policy["safety_bypass_source"] == "env:PEEKXD_SAFETY_MCP=1;trusted_bootstrap=false"
