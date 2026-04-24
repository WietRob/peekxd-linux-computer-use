"""Tests for Orchestrator Ghost Live Overlay integration (Softbox V3)."""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock

from peekxd.agent.orchestrator import AgentOrchestrator
from peekxd.core.safety import SafetyLevel
from peekxd.core.overlay import OverlayDecision, OverlayRequest


def _make_orchestrator(**kwargs):
    """Create an orchestrator with all providers mocked."""
    defaults = {
        "max_steps": 1,
        "step_delay": 0,
        "enable_memory": False,
        "enable_audit": False,
        "enable_cleanup": False,
        "vision_provider": MagicMock(),
        "screenshot_provider": MagicMock(),
        "input_provider": MagicMock(),
        "window_provider": MagicMock(),
    }
    defaults.update(kwargs)
    return AgentOrchestrator(**defaults)


def _make_destructive_plan():
    """Plan that triggers GHOST zone (destructive pattern)."""
    return {"action": "type", "params": {"text": "rm -rf /"}, "reason": "test"}


def _make_shadow_plan():
    """Plan that triggers SHADOW zone (normal type)."""
    return {"action": "type", "params": {"text": "hello"}, "reason": "test"}


def _make_direct_plan():
    """Plan that triggers DIRECT zone (capture_screen)."""
    return {"action": "capture_screen", "params": {}, "reason": "test"}


def _screen_state():
    return {"path": "/tmp/test_screen.png", "description": "test screen"}


class TestGhostNoOverlay:
    """GHOST without overlay stays the same as V2."""

    def test_ghost_without_overlay_does_not_execute(self):
        orch = _make_orchestrator(force_ghost=False, enable_ghost_overlay=False)
        orch._execute_action = MagicMock(return_value={"success": True})

        result = orch._act(_make_destructive_plan(), _screen_state())

        assert result["ghost"] is True
        assert result["blocked"] is True
        assert result["executed"] is False
        orch._execute_action.assert_not_called()

    def test_ghost_result_has_no_overlay_decision(self):
        orch = _make_orchestrator(enable_ghost_overlay=False)
        result = orch._act(_make_destructive_plan(), _screen_state())

        assert "overlay_decision" not in result


class TestGhostWithOverlay:
    """GHOST with overlay enabled."""

    def _make_orch_with_mock_overlay(self, overlay_decision=None):
        orch = _make_orchestrator(enable_ghost_overlay=True, ghost_overlay_timeout=3)
        if overlay_decision is None:
            overlay_decision = OverlayDecision(
                approved=True, backend="noop", reason="test"
            )
        mock_ctrl = MagicMock()
        mock_ctrl.show_preview.return_value = overlay_decision
        orch._overlay_controller = mock_ctrl
        return orch

    def test_overlay_controller_is_called(self):
        orch = self._make_orch_with_mock_overlay()

        result = orch._act(_make_destructive_plan(), _screen_state())

        orch._overlay_controller.show_preview.assert_called_once()
        call_args = orch._overlay_controller.show_preview.call_args
        req = call_args[0][0]
        assert isinstance(req, OverlayRequest)
        assert req.action == "type"

    def test_approved_does_not_execute(self):
        """V3: even approved=True does not execute the action."""
        orch = self._make_orch_with_mock_overlay(
            overlay_decision=OverlayDecision(approved=True, backend="tkinter", reason="User approved")
        )
        orch._execute_action = MagicMock(return_value={"success": True})

        result = orch._act(_make_destructive_plan(), _screen_state())

        # GHOST stays non-executing even after approval
        assert result["ghost"] is True
        assert result["blocked"] is True
        assert result["executed"] is False
        orch._execute_action.assert_not_called()

    def test_cancelled_does_not_execute(self):
        orch = self._make_orch_with_mock_overlay(
            overlay_decision=OverlayDecision(cancelled=True, backend="tkinter", reason="User cancelled")
        )
        orch._execute_action = MagicMock()

        result = orch._act(_make_destructive_plan(), _screen_state())

        assert result["ghost"] is True
        assert result["blocked"] is True
        orch._execute_action.assert_not_called()

    def test_timed_out_does_not_execute(self):
        orch = self._make_orch_with_mock_overlay(
            overlay_decision=OverlayDecision(timed_out=True, backend="noop", reason="Timeout")
        )
        orch._execute_action = MagicMock()

        result = orch._act(_make_destructive_plan(), _screen_state())

        assert result["ghost"] is True
        assert result["blocked"] is True
        orch._execute_action.assert_not_called()

    def test_overlay_decision_in_result(self):
        orch = self._make_orch_with_mock_overlay(
            overlay_decision=OverlayDecision(approved=False, cancelled=True, backend="tkinter", reason="User cancelled")
        )

        result = orch._act(_make_destructive_plan(), _screen_state())

        assert "overlay_decision" in result
        assert result["overlay_decision"]["cancelled"] is True
        assert result["overlay_decision"]["backend"] == "tkinter"

    def test_overlay_decision_in_audit(self):
        orch = _make_orchestrator(enable_ghost_overlay=True, enable_audit=True)
        mock_ctrl = MagicMock()
        mock_ctrl.show_preview.return_value = OverlayDecision(
            timed_out=True, backend="noop", reason="Timeout"
        )
        orch._overlay_controller = mock_ctrl

        result = orch._act(_make_destructive_plan(), _screen_state())

        assert orch.audit is not None
        # AuditLogger stores entries in .actions, not .entries
        entries = orch.audit.actions
        assert len(entries) > 0
        entry = entries[-1]
        assert entry.result.get("overlay_decision") is not None
        assert entry.result.get("executed") is False

    def test_force_ghost_with_overlay(self):
        """force_ghost=True + enable_ghost_overlay=True triggers overlay."""
        orch = _make_orchestrator(force_ghost=True, enable_ghost_overlay=True)
        mock_ctrl = MagicMock()
        mock_ctrl.show_preview.return_value = OverlayDecision(
            timed_out=True, backend="noop", reason="Timeout"
        )
        orch._overlay_controller = mock_ctrl

        # Even a safe action should be forced to GHOST
        result = orch._act(_make_direct_plan(), _screen_state())

        assert result["ghost"] is True
        assert "overlay_decision" in result


class TestShadowUnchanged:
    """SHADOW zone must not trigger overlay."""

    def test_shadow_no_overlay(self):
        orch = _make_orchestrator(enable_ghost_overlay=True)
        mock_ctrl = MagicMock()
        orch._overlay_controller = mock_ctrl
        orch._execute_action = MagicMock(return_value={"success": True, "detail": "ok"})

        # Need screenshot for shadow
        orch._screenshot_prov = MagicMock()

        result = orch._act(_make_shadow_plan(), _screen_state())

        # Shadow result should not have overlay_decision
        assert "overlay_decision" not in result
        # Overlay controller should NOT have been called
        mock_ctrl.show_preview.assert_not_called()


class TestDirectUnchanged:
    """DIRECT zone must not trigger overlay."""

    def test_direct_no_overlay(self):
        orch = _make_orchestrator(enable_ghost_overlay=True)
        mock_ctrl = MagicMock()
        orch._overlay_controller = mock_ctrl
        orch._execute_action = MagicMock(return_value={"success": True, "detail": "ok"})

        result = orch._act(_make_direct_plan(), _screen_state())

        assert "overlay_decision" not in result
        mock_ctrl.show_preview.assert_not_called()
