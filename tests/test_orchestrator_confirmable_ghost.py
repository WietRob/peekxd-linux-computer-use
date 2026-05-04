"""Tests for Orchestrator V4 Confirmable Ghost Action integration (Softbox V4).

NOTE: These tests mock safety.check_zone to force GHOST zone with empty risk
factors. This tests the GHOST-branch V4 logic in isolation. For tests that
use REAL ZoneDecision.decide() and prove the SHADOW-to-confirmable routing
path, see test_real_confirmable_ghost.py.

Tests the 13 mandatory V4 confirmable ghost action cases:
 1. Normal click + overlay approved=True -> _execute_action called exactly once
 2. Normal type + overlay approved=True -> _execute_action called exactly once
 3. approved=False -> no execution
 4. timed_out=True -> no execution
 5. cancelled=True -> no execution
 6. Destructive type "rm -rf /" + approved=True -> no execution
 7. Credential text + approved=True -> no execution
 8. Protected path + approved=True -> no execution
 9. Unknown action + approved=True -> no execution
10. force_ghost=True + approved=True -> no execution
11. Audit contains overlay_decision, approval_execution_decision, executed flag
12. V2 Shadow remains unchanged (shadow test still passes)
13. V3 Preview-only behavior preserved when enable_ghost_approval_execution=False
"""

import pytest
from unittest.mock import MagicMock, patch

from peekxd.agent.orchestrator import AgentOrchestrator
from peekxd.core.overlay import OverlayDecision, OverlayRequest
from peekxd.core.zones import (
    Zone,
    RiskDecision,
    GhostActionClassification,
    GhostApprovalDecision,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_orchestrator(**kwargs):
    """Create an orchestrator with all providers mocked."""
    defaults = {
        "max_steps": 1,
        "step_delay": 0,
        "enable_memory": False,
        "enable_audit": True,
        "enable_cleanup": False,
        "vision_provider": MagicMock(),
        "screenshot_provider": MagicMock(),
        "input_provider": MagicMock(),
        "window_provider": MagicMock(),
    }
    defaults.update(kwargs)
    return AgentOrchestrator(**defaults)


def _screen_state():
    return {"path": "/tmp/test_screen.png", "description": "test screen"}


def _ghost_zone_decision(risk_factors=None):
    """Build a GHOST-zone RiskDecision with optional risk factors."""
    return RiskDecision(
        zone=Zone.GHOST,
        risk_level="warn",
        risk_factors=risk_factors or [],
        reason="forced to GHOST zone for testing",
    )


def _make_v4_orch(overlay_decision, *, force_ghost=False, enable_audit=True):
    """Create a V4 orchestrator with mocked overlay and safety returning GHOST.

    The safety.check_zone is mocked to return a GHOST zone decision with NO
    risk factors so the action is classified as APPROVABLE_GHOST.
    """
    orch = _make_orchestrator(
        enable_ghost_overlay=True,
        enable_ghost_approval_execution=True,
        enable_audit=enable_audit,
        force_ghost=force_ghost,
        ghost_overlay_timeout=3,
    )
    # Mock overlay controller
    mock_ctrl = MagicMock()
    mock_ctrl.show_preview.return_value = overlay_decision
    orch._overlay_controller = mock_ctrl
    # Mock safety.check_zone to return GHOST zone with empty risk factors
    orch.safety.check_zone = MagicMock(return_value=_ghost_zone_decision([]))
    # Mock _execute_action
    orch._execute_action = MagicMock(return_value={"success": True, "detail": "ok"})
    return orch


# ===========================================================================
# Test 1: Normal click + overlay approved=True -> _execute_action called once
# ===========================================================================

class TestV4ConfirmableGhostClickApproved:
    """Test 1: Normal click approved via overlay executes once."""

    def test_click_approved_executes_once(self):
        orch = _make_v4_orch(
            OverlayDecision(approved=True, backend="tkinter", reason="User approved"),
        )

        plan = {"action": "click", "params": {"x": 100, "y": 200}, "reason": "test"}
        result = orch._act(plan, _screen_state())

        orch._execute_action.assert_called_once()
        assert result["executed"] is True
        assert result["blocked"] is False
        assert result["ghost"] is True


# ===========================================================================
# Test 2: Normal type + overlay approved=True -> _execute_action called once
# ===========================================================================

class TestV4ConfirmableGhostTypeApproved:
    """Test 2: Normal type approved via overlay executes once."""

    def test_type_approved_executes_once(self):
        orch = _make_v4_orch(
            OverlayDecision(approved=True, backend="tkinter", reason="User approved"),
        )

        plan = {"action": "type", "params": {"text": "hello world"}, "reason": "test"}
        result = orch._act(plan, _screen_state())

        orch._execute_action.assert_called_once()
        assert result["executed"] is True
        assert result["blocked"] is False
        assert result["ghost"] is True


# ===========================================================================
# Test 3: approved=False -> no execution
# ===========================================================================

class TestV4ConfirmableGhostNotApproved:
    """Test 3: approved=False -> no execution."""

    def test_not_approved_no_execution(self):
        orch = _make_v4_orch(
            OverlayDecision(approved=False, backend="tkinter", reason="User rejected"),
        )

        plan = {"action": "click", "params": {"x": 100, "y": 200}, "reason": "test"}
        result = orch._act(plan, _screen_state())

        orch._execute_action.assert_not_called()
        assert result["executed"] is False
        assert result["blocked"] is True


# ===========================================================================
# Test 4: timed_out=True -> no execution
# ===========================================================================

class TestV4ConfirmableGhostTimedOut:
    """Test 4: timed_out=True -> no execution."""

    def test_timed_out_no_execution(self):
        orch = _make_v4_orch(
            OverlayDecision(timed_out=True, backend="noop", reason="Timeout"),
        )

        plan = {"action": "click", "params": {"x": 100, "y": 200}, "reason": "test"}
        result = orch._act(plan, _screen_state())

        orch._execute_action.assert_not_called()
        assert result["executed"] is False
        assert result["blocked"] is True


# ===========================================================================
# Test 5: cancelled=True -> no execution
# ===========================================================================

class TestV4ConfirmableGhostCancelled:
    """Test 5: cancelled=True -> no execution."""

    def test_cancelled_no_execution(self):
        orch = _make_v4_orch(
            OverlayDecision(cancelled=True, backend="tkinter", reason="User cancelled"),
        )

        plan = {"action": "click", "params": {"x": 100, "y": 200}, "reason": "test"}
        result = orch._act(plan, _screen_state())

        orch._execute_action.assert_not_called()
        assert result["executed"] is False
        assert result["blocked"] is True


# ===========================================================================
# Test 6: Destructive type "rm -rf /" + approved=True -> no execution
# ===========================================================================

class TestV4HardBlockedDestructive:
    """Test 6: Destructive type always hard-blocked even with approval."""

    def test_destructive_type_not_executed(self):
        orch = _make_orchestrator(
            enable_ghost_overlay=True,
            enable_ghost_approval_execution=True,
            enable_audit=True,
            ghost_overlay_timeout=3,
        )
        # Mock overlay controller returning approved
        mock_ctrl = MagicMock()
        mock_ctrl.show_preview.return_value = OverlayDecision(
            approved=True, backend="tkinter", reason="User approved",
        )
        orch._overlay_controller = mock_ctrl
        orch._execute_action = MagicMock(return_value={"success": True})

        # Use actual safety.check_zone — "rm -rf /" triggers destructive pattern -> GHOST
        plan = {"action": "type", "params": {"text": "rm -rf /"}, "reason": "test"}
        result = orch._act(plan, _screen_state())

        orch._execute_action.assert_not_called()
        assert result["executed"] is False
        assert result["blocked"] is True


# ===========================================================================
# Test 7: Credential text + approved=True -> no execution
# ===========================================================================

class TestV4HardBlockedCredential:
    """Test 7: Credential text always hard-blocked even with approval."""

    def test_credential_text_not_executed(self):
        orch = _make_orchestrator(
            enable_ghost_overlay=True,
            enable_ghost_approval_execution=True,
            enable_audit=True,
            ghost_overlay_timeout=3,
        )
        mock_ctrl = MagicMock()
        mock_ctrl.show_preview.return_value = OverlayDecision(
            approved=True, backend="tkinter", reason="User approved",
        )
        orch._overlay_controller = mock_ctrl
        orch._execute_action = MagicMock(return_value={"success": True})

        # "password=secret123" triggers credential pattern -> GHOST zone with risk factors
        plan = {"action": "type", "params": {"text": "password=secret123"}, "reason": "test"}
        result = orch._act(plan, _screen_state())

        orch._execute_action.assert_not_called()
        assert result["executed"] is False
        assert result["blocked"] is True


# ===========================================================================
# Test 8: Protected path + approved=True -> no execution
# ===========================================================================

class TestV4HardBlockedProtectedPath:
    """Test 8: Protected path always hard-blocked even with approval."""

    def test_protected_path_not_executed(self):
        orch = _make_orchestrator(
            enable_ghost_overlay=True,
            enable_ghost_approval_execution=True,
            enable_audit=True,
            ghost_overlay_timeout=3,
        )
        mock_ctrl = MagicMock()
        mock_ctrl.show_preview.return_value = OverlayDecision(
            approved=True, backend="tkinter", reason="User approved",
        )
        orch._overlay_controller = mock_ctrl
        orch._execute_action = MagicMock(return_value={"success": True})

        # output_path="/etc/passwd.png" triggers protected path -> GHOST with risk factors
        plan = {"action": "capture_screen", "params": {"output_path": "/etc/passwd.png"}, "reason": "test"}
        result = orch._act(plan, _screen_state())

        orch._execute_action.assert_not_called()
        assert result["executed"] is False
        assert result["blocked"] is True


# ===========================================================================
# Test 9: Unknown action + approved=True -> no execution
# ===========================================================================

class TestV4HardBlockedUnknown:
    """Test 9: Unknown action always hard-blocked even with approval."""

    def test_unknown_action_not_executed(self):
        orch = _make_orchestrator(
            enable_ghost_overlay=True,
            enable_ghost_approval_execution=True,
            enable_audit=True,
            ghost_overlay_timeout=3,
        )
        mock_ctrl = MagicMock()
        mock_ctrl.show_preview.return_value = OverlayDecision(
            approved=True, backend="tkinter", reason="User approved",
        )
        orch._overlay_controller = mock_ctrl
        orch._execute_action = MagicMock(return_value={"success": True})

        # "delete_everything" is not a known action -> unknown_action risk factor -> GHOST
        plan = {"action": "delete_everything", "params": {}, "reason": "test"}
        result = orch._act(plan, _screen_state())

        orch._execute_action.assert_not_called()
        assert result["executed"] is False
        assert result["blocked"] is True


# ===========================================================================
# Test 10: force_ghost=True + approved=True -> no execution
# ===========================================================================

class TestV4ForceGhostBlocks:
    """Test 10: force_ghost=True always hard-blocks even with approval."""

    def test_force_ghost_not_executed(self):
        orch = _make_v4_orch(
            OverlayDecision(approved=True, backend="tkinter", reason="User approved"),
            force_ghost=True,
        )

        plan = {"action": "click", "params": {"x": 100, "y": 200}, "reason": "test"}
        result = orch._act(plan, _screen_state())

        orch._execute_action.assert_not_called()
        assert result["executed"] is False
        assert result["blocked"] is True


# ===========================================================================
# Test 11: Audit contains overlay_decision, approval_execution_decision, executed flag
# ===========================================================================

class TestV4AuditEntries:
    """Test 11: Audit entries contain V4 fields."""

    def test_audit_approved_executed_has_fields(self):
        """Approved APPROVABLE action: audit has overlay_decision, approval_execution_decision, executed=True."""
        orch = _make_v4_orch(
            OverlayDecision(approved=True, backend="tkinter", reason="User approved"),
        )

        plan = {"action": "click", "params": {"x": 100, "y": 200}, "reason": "test"}
        result = orch._act(plan, _screen_state())

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
        assert entry.result.get("executed") is True

    def test_audit_blocked_has_executed_false(self):
        """Blocked action: audit has executed=False."""
        orch = _make_v4_orch(
            OverlayDecision(cancelled=True, backend="tkinter", reason="User cancelled"),
        )

        plan = {"action": "click", "params": {"x": 100, "y": 200}, "reason": "test"}
        orch._act(plan, _screen_state())

        entry = orch.audit.actions[-1]
        audit_res = entry.result

        assert "overlay_decision" in audit_res
        assert audit_res["overlay_decision"]["cancelled"] is True
        assert "approval_execution_decision" in audit_res
        assert audit_res["approval_execution_decision"]["should_execute"] is False
        assert audit_res["approval_execution_decision"]["executed"] is False


# ===========================================================================
# Test 12: V2 Shadow remains unchanged
# ===========================================================================

class TestV2ShadowUnchanged:
    """Test 12: V2 Shadow behavior is preserved when V4 flags are off."""

    def test_shadow_click_executes_normally(self):
        """Normal click goes through SHADOW zone and executes with V4 flags off."""
        orch = _make_orchestrator(
            enable_ghost_overlay=False,
            enable_ghost_approval_execution=False,
            enable_audit=True,
        )
        orch._execute_action = MagicMock(return_value={"success": True, "detail": "clicked"})
        orch._screenshot_prov = MagicMock()

        plan = {"action": "click", "params": {"x": 100, "y": 200}, "reason": "test"}
        result = orch._act(plan, _screen_state())

        orch._execute_action.assert_called_once()
        assert result.get("success") is True
        # Shadow metadata present
        assert "shadow" in result
        # No overlay_decision in result
        assert "overlay_decision" not in result

    def test_shadow_type_executes_normally(self):
        """Normal type goes through SHADOW zone and executes."""
        orch = _make_orchestrator(
            enable_ghost_overlay=False,
            enable_ghost_approval_execution=False,
            enable_audit=True,
        )
        orch._execute_action = MagicMock(return_value={"success": True, "detail": "typed"})
        orch._screenshot_prov = MagicMock()

        plan = {"action": "type", "params": {"text": "hello"}, "reason": "test"}
        result = orch._act(plan, _screen_state())

        orch._execute_action.assert_called_once()
        assert result.get("success") is True
        assert "shadow" in result


# ===========================================================================
# Test 13: V3 Preview-only preserved when enable_ghost_approval_execution=False
# ===========================================================================

class TestV3PreviewOnlyPreserved:
    """Test 13: V3 behavior — overlay shown but action never executes."""

    def test_v3_overlay_approved_does_not_execute(self):
        """enable_ghost_overlay=True but enable_ghost_approval_execution=False:
        even with approved=True, _execute_action is NOT called."""
        orch = _make_orchestrator(
            enable_ghost_overlay=True,
            enable_ghost_approval_execution=False,
            enable_audit=True,
            ghost_overlay_timeout=3,
        )
        mock_ctrl = MagicMock()
        mock_ctrl.show_preview.return_value = OverlayDecision(
            approved=True, backend="tkinter", reason="User approved",
        )
        orch._overlay_controller = mock_ctrl
        orch._execute_action = MagicMock(return_value={"success": True})

        # Force GHOST zone via safety mock (no risk factors)
        orch.safety.check_zone = MagicMock(return_value=_ghost_zone_decision([]))

        plan = {"action": "click", "params": {"x": 100, "y": 200}, "reason": "test"}
        result = orch._act(plan, _screen_state())

        # Overlay was shown
        mock_ctrl.show_preview.assert_called_once()
        # But action was NOT executed — V3 preview-only behavior
        orch._execute_action.assert_not_called()
        assert result["executed"] is False
        assert result["blocked"] is True
        assert result["ghost"] is True
