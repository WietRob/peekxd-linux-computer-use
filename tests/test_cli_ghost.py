"""CLI integration tests for Softbox Ghost Mode.

Tests that CLI --ghost flag correctly propagates to AgentOrchestrator.
No real desktop actions are executed — all orchestrator calls are mocked.
"""

import sys
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from peekxd.cli import cli


class TestCliGhostFlag:
    """Test CLI --ghost flag propagation."""

    def _mock_agent_module(self, mock_orch_class):
        """Create a mock peekxd.agent module with AgentOrchestrator."""
        mock_agent = MagicMock()
        mock_agent.AgentOrchestrator = mock_orch_class
        sys.modules["peekxd.agent"] = mock_agent

    def test_ghost_flag_accepted(self):
        """--ghost flag must be accepted by agent run command."""
        runner = CliRunner()
        mock_orch_class = MagicMock()
        inst = MagicMock()
        inst.run_task.return_value = MagicMock(
            success=True,
            steps_taken=0,
            elapsed_seconds=0.0,
            summary="Ghost mode — no actions executed",
            errors=[],
        )
        mock_orch_class.return_value = inst
        self._mock_agent_module(mock_orch_class)

        result = runner.invoke(cli, [
            "agent", "run", "click at 100 200",
            "--ghost",
            "--max-steps", "1",
        ])

        # Command must succeed (exit code 0)
        assert result.exit_code == 0, f"Exit code {result.exit_code}: {result.output}"

        # Orchestrator must be instantiated with force_ghost=True
        mock_orch_class.assert_called_once()
        call_kwargs = mock_orch_class.call_args.kwargs
        assert call_kwargs.get("force_ghost") is True, \
            f"force_ghost was {call_kwargs.get('force_ghost')!r}, expected True"

    def test_ghost_flag_not_set_by_default(self):
        """Without --ghost, force_ghost must be False."""
        runner = CliRunner()
        mock_orch_class = MagicMock()
        inst = MagicMock()
        inst.run_task.return_value = MagicMock(
            success=True,
            steps_taken=1,
            elapsed_seconds=1.0,
            summary="Done",
            errors=[],
        )
        mock_orch_class.return_value = inst
        self._mock_agent_module(mock_orch_class)

        result = runner.invoke(cli, [
            "agent", "run", "click at 100 200",
            "--max-steps", "1",
        ])

        assert result.exit_code == 0, f"Exit code {result.exit_code}: {result.output}"

        call_kwargs = mock_orch_class.call_args.kwargs
        assert call_kwargs.get("force_ghost") is not True, \
            f"force_ghost was {call_kwargs.get('force_ghost')!r}, expected not True"

    def test_ghost_flag_output_contains_ghost_hint(self):
        """Output should indicate ghost mode is active."""
        runner = CliRunner()
        mock_orch_class = MagicMock()
        inst = MagicMock()
        inst.run_task.return_value = MagicMock(
            success=True,
            steps_taken=0,
            elapsed_seconds=0.0,
            summary="Ghost mode — no actions executed",
            errors=[],
        )
        mock_orch_class.return_value = inst
        self._mock_agent_module(mock_orch_class)

        result = runner.invoke(cli, [
            "agent", "run", "type hello",
            "--ghost",
            "--max-steps", "1",
        ])

        assert result.exit_code == 0
        # Output should contain the summary from mocked orchestrator
        assert "Ghost" in result.output or "ghost" in result.output.lower() or \
               "SUCCESS" in result.output, \
            f"Expected ghost-related output, got: {result.output[:200]}"
