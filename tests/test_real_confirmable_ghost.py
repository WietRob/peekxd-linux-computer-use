"""Tests for Softbox V4 Confirmable Ghost Actions — REAL non-mock tests.

These tests use the REAL ZoneDecision.decide() and do NOT mock
safety.check_zone. The only mocking is for _execute_action and
overlay controller (since we can't show a real GUI in tests).

This proves that APPROVABLE_GHOST is reachable in the real
Orchestrator flow when a safe SHADOW-zone action is routed
through the confirmable-ghost path.
"""

import pytest
from unittest.mock import MagicMock

from peekxd.agent.orchestrator import AgentOrchestrator
from peekxd.core.overlay import OverlayDecision
from peekxd.core.zones import (
    Zone,
    RiskDecision,
    GhostActionClassification,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_real_orch(overlay_decision, *, enable_audit=True, force_ghost=False):
    """Create an orchestrator with REAL zone decisions, mocked overlay + execution.

    Key difference from test_orchestrator_confirmable_ghost:
    - safety.check_zone is NOT mocked — real ZoneDecision.decide() is used
    - Only _execute_action and overlay controller are mocked
    """
    orch = AgentOrchestrator(
        max_steps=1,
        step_delay=0,
        enable_memory=False,
        enable_audit=enable_audit,
        enable_cleanup=False,
        vision_provider=MagicMock(),
        screenshot_provider=MagicMock(),
        input_provider=MagicMock(),
        window_provider=MagicMock(),
        enable_ghost_overlay=True,
        enable_ghost_approval_execution=True,
        force_ghost=force_ghost,
        ghost_overlay_timeout=3,
    )
    # Mock overlay controller
    mock_ctrl = MagicMock()
    mock_ctrl.show_preview.return_value = overlay_decision
    orch._overlay_controller = mock_ctrl
    # Mock _execute_action
    orch._execute_action = MagicMock(return_value={"success": True, "detail": "ok"})
    return orch


def _screen_state():
    return {"path": "/tmp/test_screen.png", "description": "test screen"}


# ===========================================================================
# Test 1: Real safe click + approval execution on + approved=True → executes once
# ===========================================================================

class TestRealConfirmableGhostClickApproved:
    """Real click (SHADOW zone) routed through confirmable ghost → executes."""

    def test_click_approved_executes_once(self):
        orch = _make_real_orch(
            OverlayDecision(approved=True, backend="tkinter", reason="User approved"),
        )
        # Real ZoneDecision: click → SHADOW, risk_factors=[]
        plan = {"action": "click", "params": {"x": 100, "y": 200}, "reason": "test"}
        result = orch._act(plan, _screen_state())

        orch._execute_action.assert_called_once()
        assert result["executed"] is True
        assert result["blocked"] is False
        assert result["ghost"] is True
        assert result["approval_execution_decision"]["should_execute"] is True
        assert result["approval_execution_decision"]["executed"] is True


# ===========================================================================
# Test 2: Real safe type + approval execution on + approved=True → executes once
# ===========================================================================

class TestRealConfirmableGhostTypeApproved:
    """Real type (SHADOW zone) routed through confirmable ghost → executes."""

    def test_type_approved_executes_once(self):
        orch = _make_real_orch(
            OverlayDecision(approved=True, backend="tkinter", reason="User approved"),
        )
        # Real ZoneDecision: type "hello" → SHADOW, risk_factors=[]
        plan = {"action": "type", "params": {"text": "hello"}, "reason": "test"}
        result = orch._act(plan, _screen_state())

        orch._execute_action.assert_called_once()
        assert result["executed"] is True
        assert result["blocked"] is False


# ===========================================================================
# Test 3: Real safe click + approval flag OFF → normal SHADOW behavior unchanged
# ===========================================================================

class TestRealShadowUnchangedWithoutApprovalFlag:
    """With enable_ghost_approval_execution=False, SHADOW behavior is unchanged."""

    def test_click_without_approval_flag_executes_normally(self):
        orch = AgentOrchestrator(
            max_steps=1,
            step_delay=0,
            enable_memory=False,
            enable_audit=True,
            enable_cleanup=False,
            vision_provider=MagicMock(),
            screenshot_provider=MagicMock(),
            input_provider=MagicMock(),
            window_provider=MagicMock(),
            enable_ghost_overlay=True,
            enable_ghost_approval_execution=False,  # OFF
        )
        orch._execute_action = MagicMock(return_value={"success": True, "detail": "clicked"})
        orch._screenshot_prov = MagicMock()

        plan = {"action": "click", "params": {"x": 100, "y": 200}, "reason": "test"}
        result = orch._act(plan, _screen_state())

        # Normal shadow execution (shadow recorder wraps _execute_action)
        orch._execute_action.assert_called_once()
        assert result.get("success") is True
        assert "shadow" in result
        assert "overlay_decision" not in result


# ===========================================================================
# Test 4: Real safe click + approved=False → no execution
# ===========================================================================

class TestRealConfirmableGhostNotApproved:
    """Real click, overlay returns approved=False → no execution."""

    def test_click_not_approved_no_execution(self):
        orch = _make_real_orch(
            OverlayDecision(approved=False, backend="tkinter", reason="User rejected"),
        )
        plan = {"action": "click", "params": {"x": 100, "y": 200}, "reason": "test"}
        result = orch._act(plan, _screen_state())

        orch._execute_action.assert_not_called()
        assert result["executed"] is False
        assert result["blocked"] is True


# ===========================================================================
# Test 5: Real safe click + timed_out=True → no execution
# ===========================================================================

class TestRealConfirmableGhostTimedOut:
    """Real click, overlay times out → no execution."""

    def test_click_timed_out_no_execution(self):
        orch = _make_real_orch(
            OverlayDecision(timed_out=True, backend="noop", reason="Timeout"),
        )
        plan = {"action": "click", "params": {"x": 100, "y": 200}, "reason": "test"}
        result = orch._act(plan, _screen_state())

        orch._execute_action.assert_not_called()
        assert result["executed"] is False
        assert result["blocked"] is True

    def test_click_overlay_ignores_stale_screenshot_path(self):
        """Confirmable-ghost routing stays semantic-only when screenshot is absent."""
        orch = _make_real_orch(
            OverlayDecision(timed_out=True, backend="noop", reason="Timeout"),
        )
        orch._screenshot_prov = None
        plan = {"action": "click", "params": {"x": 100, "y": 200}, "reason": "test"}
        result = orch._act(
            plan,
            {"path": "/tmp/stale-shadow-screen.png", "description": "semantic screen"},
        )

        assert result["executed"] is False
        mock_ctrl = orch._overlay_controller
        assert isinstance(mock_ctrl, MagicMock)
        mock_ctrl.show_preview.assert_called_once()
        request = mock_ctrl.show_preview.call_args.args[0]
        assert request.screenshot_path is None


# ===========================================================================
# Test 6: Real destructive type + approved=True → no execution
# ===========================================================================

class TestRealDestructiveTypeHardBlocked:
    """Destructive type ("rm -rf /") → GHOST zone with risk factors → HARD_BLOCKED."""

    def test_destructive_type_not_executed(self):
        orch = _make_real_orch(
            OverlayDecision(approved=True, backend="tkinter", reason="User approved"),
        )
        # Real ZoneDecision: type "rm -rf /" → GHOST, risk_factors=["destructive_pattern: 'rm '"]
        plan = {"action": "type", "params": {"text": "rm -rf /"}, "reason": "test"}
        result = orch._act(plan, _screen_state())

        orch._execute_action.assert_not_called()
        assert result["executed"] is False
        assert result["blocked"] is True


# ===========================================================================
# Test 7: Real credential type + approved=True → no execution
# ===========================================================================

class TestRealCredentialTypeHardBlocked:
    """Credential type ("password=secret") → GHOST zone with risk factors → HARD_BLOCKED."""

    def test_credential_type_not_executed(self):
        orch = _make_real_orch(
            OverlayDecision(approved=True, backend="tkinter", reason="User approved"),
        )
        # Real ZoneDecision: type "password=secret123" → GHOST, risk_factors=["credential_pattern: 'password'"]
        plan = {"action": "type", "params": {"text": "password=secret123"}, "reason": "test"}
        result = orch._act(plan, _screen_state())

        orch._execute_action.assert_not_called()
        assert result["executed"] is False
        assert result["blocked"] is True


# ===========================================================================
# Test 8: force_ghost=True + safe click + approved=True → no execution
# ===========================================================================

class TestRealForceGhostBlocks:
    """force_ghost=True forces GHOST zone, always HARD_BLOCKED."""

    def test_force_ghost_not_executed(self):
        orch = _make_real_orch(
            OverlayDecision(approved=True, backend="tkinter", reason="User approved"),
            force_ghost=True,
        )
        plan = {"action": "click", "params": {"x": 100, "y": 200}, "reason": "test"}
        result = orch._act(plan, _screen_state())

        orch._execute_action.assert_not_called()
        assert result["executed"] is False
        assert result["blocked"] is True


# ===========================================================================
# Test 9: unknown action + approved=True → no execution
# ===========================================================================

class TestRealUnknownActionHardBlocked:
    """Unknown action → GHOST zone with risk factors → HARD_BLOCKED."""

    def test_unknown_action_not_executed(self):
        orch = _make_real_orch(
            OverlayDecision(approved=True, backend="tkinter", reason="User approved"),
        )
        # Real ZoneDecision: "delete_everything" → GHOST, risk_factors=["unknown_action: delete_everything"]
        plan = {"action": "delete_everything", "params": {}, "reason": "test"}
        result = orch._act(plan, _screen_state())

        orch._execute_action.assert_not_called()
        assert result["executed"] is False
        assert result["blocked"] is True


# ===========================================================================
# Test 10: Audit trail for real approved execution
# ===========================================================================

class TestRealAuditTrail:
    """Audit entries contain V4 fields for real approved execution."""

    def test_audit_approved_click_has_all_fields(self):
        orch = _make_real_orch(
            OverlayDecision(approved=True, backend="tkinter", reason="User approved"),
        )
        plan = {"action": "click", "params": {"x": 100, "y": 200}, "reason": "test"}
        orch._act(plan, _screen_state())

        assert orch.audit is not None
        entries = orch.audit.actions
        assert len(entries) > 0
        entry = entries[-1]
        audit_res = entry.result

        assert "overlay_decision" in audit_res
        assert audit_res["overlay_decision"]["approved"] is True
        assert "approval_execution_decision" in audit_res
        assert audit_res["approval_execution_decision"]["should_execute"] is True
        assert audit_res["approval_execution_decision"]["executed"] is True
        assert audit_res["approval_execution_decision"]["classification"]["classification"] == "approvable_ghost"
        assert audit_res["zone"] == "shadow_confirmable_ghost"
        assert audit_res["executed"] is True
