"""Tests for CLI Ghost Live Overlay flags (Softbox V3)."""

from click.testing import CliRunner

from peekxd.cli import cli


class TestCliOverlayFlags:
    """Test --ghost-overlay CLI flags."""

    def test_ghost_overlay_accepted(self):
        runner = CliRunner()
        # --help should show the flag
        result = runner.invoke(cli, ["agent", "run", "--help"])
        assert result.exit_code == 0
        assert "--ghost-overlay" in result.output

    def test_ghost_overlay_timeout_accepted(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["agent", "run", "--help"])
        assert result.exit_code == 0
        assert "--ghost-overlay-timeout" in result.output

    def test_ghost_overlay_backend_accepted(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["agent", "run", "--help"])
        assert result.exit_code == 0
        assert "--ghost-overlay-backend" in result.output

    def test_default_no_overlay(self):
        """Without --ghost-overlay, enable_ghost_overlay should be False."""
        from peekxd.agent.orchestrator import AgentOrchestrator
        orch = AgentOrchestrator(max_steps=1, enable_audit=False, enable_memory=False)
        assert orch.enable_ghost_overlay is False

    def test_ghost_and_overlay_combined(self):
        """--ghost + --ghost-overlay should set both flags."""
        from peekxd.agent.orchestrator import AgentOrchestrator
        orch = AgentOrchestrator(
            max_steps=1,
            force_ghost=True,
            enable_ghost_overlay=True,
            ghost_overlay_timeout=7,
            enable_audit=False,
            enable_memory=False,
        )
        assert orch.force_ghost is True
        assert orch.enable_ghost_overlay is True
        assert orch.ghost_overlay_timeout == 7

    def test_overlay_timeout_value(self):
        """ghost_overlay_timeout should accept custom value."""
        from peekxd.agent.orchestrator import AgentOrchestrator
        orch = AgentOrchestrator(
            max_steps=1,
            enable_ghost_overlay=True,
            ghost_overlay_timeout=10,
            enable_audit=False,
            enable_memory=False,
        )
        assert orch.ghost_overlay_timeout == 10
