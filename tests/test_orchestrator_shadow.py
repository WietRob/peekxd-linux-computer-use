"""Tests for orchestrator SHADOW zone integration (V2)."""

from unittest.mock import MagicMock, patch

import pytest

from peekxd.agent.orchestrator import AgentOrchestrator
from peekxd.core.safety import SafetyGuard, SafetyLevel
from peekxd.core.zones import Zone


class TestOrchestratorShadowMode:
    """Test that orchestrator correctly handles SHADOW zone actions."""

    def test_shadow_action_executes_once(self):
        """SHADOW zone action should call _execute_action exactly once (test 11)."""
        orch = AgentOrchestrator(max_steps=5)
        orch._execute_action = MagicMock(return_value={"success": True, "detail": "typed"})

        plan = {"action": "type", "params": {"text": "Hello World"}, "reason": "test"}
        screen_state = {"path": "/tmp/test.png", "description": "test screen"}

        result = orch._act(plan, screen_state)

        # _execute_action should have been called exactly once
        orch._execute_action.assert_called_once()
        assert result.get("success") is True

    def test_shadow_audit_zone_and_executed(self):
        """SHADOW audit entry should have zone=shadow and executed=True (test 12)."""
        orch = AgentOrchestrator(max_steps=5)
        orch._execute_action = MagicMock(return_value={"success": True})

        plan = {"action": "click", "params": {"x": 100, "y": 200}, "reason": "test"}
        screen_state = {"path": "/tmp/test.png", "description": "test screen"}

        orch._act(plan, screen_state)

        assert len(orch.audit.actions) == 1
        entry = orch.audit.actions[0]
        assert entry.result.get("zone") == "shadow"
        assert entry.result.get("executed") is True

    def test_shadow_contains_shadow_metadata(self):
        """SHADOW result should contain shadow metadata in action_result (test 13)."""
        orch = AgentOrchestrator(max_steps=5)
        orch._execute_action = MagicMock(return_value={"success": True, "detail": "clicked"})

        plan = {"action": "click", "params": {"x": 100, "y": 200}, "reason": "test"}
        screen_state = {"path": "/tmp/test.png", "description": "test screen"}

        result = orch._act(plan, screen_state)

        # Result should have shadow metadata
        assert "shadow" in result
        shadow = result["shadow"]
        assert "snapshot_before" in shadow
        assert "snapshot_after" in shadow
        assert "changed" in shadow
        assert "diff_summary" in shadow

    def test_shadow_click_action(self):
        """SHADOW click action should execute safely."""
        orch = AgentOrchestrator(max_steps=5)
        orch._execute_action = MagicMock(return_value={"success": True, "x": 100, "y": 200})

        plan = {"action": "click", "params": {"x": 100, "y": 200}, "reason": "test"}
        screen_state = {"path": "/tmp/test.png", "description": "test screen"}

        result = orch._act(plan, screen_state)

        orch._execute_action.assert_called_once()
        assert result.get("success") is True
        assert "shadow" in result

    def test_shadow_type_action(self):
        """SHADOW type action should execute safely."""
        orch = AgentOrchestrator(max_steps=5)
        orch._execute_action = MagicMock(return_value={"success": True, "detail": "typed 'hello'"})

        plan = {"action": "type", "params": {"text": "hello"}, "reason": "test"}
        screen_state = {"path": "/tmp/test.png", "description": "test screen"}

        result = orch._act(plan, screen_state)

        orch._execute_action.assert_called_once()
        assert result.get("success") is True
        assert "shadow" in result

    def test_shadow_safety_check_blocks_dangerous(self):
        """SHADOW safety check should block dangerous actions before execution."""
        orch = AgentOrchestrator(max_steps=5, safety_level=SafetyLevel.STRICT)
        orch._execute_action = MagicMock()

        # type with destructive text → GHOST zone (not SHADOW, risk factor pushes to GHOST)
        plan = {"action": "type", "params": {"text": "rm -rf /home"}, "reason": "test"}
        screen_state = {"path": "/tmp/test.png", "description": "test screen"}

        result = orch._act(plan, screen_state)

        # Should be GHOST, not SHADOW — destructive text triggers GHOST
        assert result.get("ghost") is True
        assert result.get("blocked") is True
        orch._execute_action.assert_not_called()

    def test_shadow_screenshot_before_in_audit(self):
        """SHADOW audit should include screenshot_before from screen_state."""
        orch = AgentOrchestrator(max_steps=5)
        orch._execute_action = MagicMock(return_value={"success": True})

        plan = {"action": "click", "params": {"x": 100, "y": 200}, "reason": "test"}
        screen_state = {"path": "/tmp/shadow_before.png", "description": "test screen"}

        orch._act(plan, screen_state)

        entry = orch.audit.actions[0]
        # screenshot_before should be set from screen_state path
        assert entry.screenshot_before is not None

    def test_shadow_action_edge_case_empty_params(self):
        """SHADOW type with empty text should still execute."""
        orch = AgentOrchestrator(max_steps=5)
        orch._execute_action = MagicMock(return_value={"success": True})

        plan = {"action": "type", "params": {"text": ""}, "reason": "test"}
        screen_state = {"path": "/tmp/test.png", "description": "test screen"}

        result = orch._act(plan, screen_state)
        orch._execute_action.assert_called_once()
        assert result.get("success") is True

    def test_shadow_without_audit_still_returns_metadata(self):
        """SHADOW should return shadow metadata even when enable_audit=False."""
        orch = AgentOrchestrator(max_steps=5, enable_audit=False)
        orch._execute_action = MagicMock(return_value={"success": True, "detail": "clicked"})

        plan = {"action": "click", "params": {"x": 100, "y": 200}, "reason": "test"}
        screen_state = {"path": "/tmp/before.png", "description": "test screen"}

        result = orch._act(plan, screen_state)

        # Action still executed
        orch._execute_action.assert_called_once()
        assert result.get("success") is True
        # Shadow metadata MUST be present even without audit
        assert "shadow" in result
        shadow = result["shadow"]
        assert "snapshot_before" in shadow
        assert "snapshot_after" in shadow
        assert "changed" in shadow
        # Audit should be None
        assert orch.audit is None

    def test_shadow_orchestrator_fallback_without_audit(self):
        """SHADOW path should work correctly when audit is disabled."""
        orch = AgentOrchestrator(max_steps=5, enable_audit=False)
        orch._execute_action = MagicMock(return_value={"success": True})

        plan = {"action": "type", "params": {"text": "Hello"}, "reason": "test"}
        screen_state = {"path": "/tmp/before.png", "description": "test screen"}

        result = orch._act(plan, screen_state)

        # Action executed with shadow metadata
        orch._execute_action.assert_called_once()
        assert result.get("success") is True
        assert "shadow" in result
        # Should not have crashed despite audit=None
        assert orch.audit is None

    def test_shadow_snapshot_error_does_not_crash_orchestrator(self):
        """Snapshot-after failure should not crash _act() — error captured in shadow."""
        orch = AgentOrchestrator(max_steps=5)
        orch._execute_action = MagicMock(return_value={"success": True})

        # Must mock _screenshot_prov directly — screenshot is a read-only @property
        # snapshot_before reuses screen_state path (no capture_fn call).
        # snapshot_after calls capture_fn once — make it fail there.
        def failing_capture(path):
            raise RuntimeError("Screenshot capture failed")

        mock_screenshot_prov = MagicMock()
        mock_screenshot_prov.capture_screen = failing_capture
        orch._screenshot_prov = mock_screenshot_prov

        # Use None path so snapshot_before also uses capture_fn and fails,
        # then snapshot_after also fails. Both errors captured in shadow.
        plan = {"action": "click", "params": {"x": 100, "y": 200}, "reason": "test"}
        screen_state = {"path": None, "description": "test screen"}

        result = orch._act(plan, screen_state)

        # Action must still execute and succeed
        orch._execute_action.assert_called_once()
        assert result.get("success") is True
        # Shadow metadata must be present
        assert "shadow" in result
        # Error must be captured, not crash
        assert result["shadow"]["error"] is not None
        assert "Screenshot capture failed" in result["shadow"]["error"]


class TestGhostRegression:
    """GHOST regression tests — GHOST must NOT execute actions (test 14)."""

    def test_destructive_type_not_executed(self):
        """Destructive type action must NOT call _execute_action."""
        orch = AgentOrchestrator(max_steps=5)
        orch._execute_action = MagicMock()

        plan = {"action": "type", "params": {"text": "sudo rm -rf /"}, "reason": "test"}
        screen_state = {"path": "/tmp/test.png", "description": "test screen"}

        result = orch._act(plan, screen_state)

        orch._execute_action.assert_not_called()
        assert result.get("ghost") is True
        assert result.get("blocked") is True

    def test_credential_text_not_executed(self):
        """Credential text must NOT call _execute_action."""
        orch = AgentOrchestrator(max_steps=5)
        orch._execute_action = MagicMock()

        plan = {"action": "type", "params": {"text": "password=secret123"}, "reason": "test"}
        screen_state = {"path": "/tmp/test.png", "description": "test screen"}

        result = orch._act(plan, screen_state)

        orch._execute_action.assert_not_called()
        assert result.get("ghost") is True

    def test_protected_path_not_executed(self):
        """Protected path screenshot must NOT call _execute_action."""
        orch = AgentOrchestrator(max_steps=5)
        orch._execute_action = MagicMock()

        plan = {"action": "capture_screen", "params": {"output_path": "/etc/passwd.png"}, "reason": "test"}
        screen_state = {"path": "/tmp/test.png", "description": "test screen"}

        result = orch._act(plan, screen_state)

        orch._execute_action.assert_not_called()
        assert result.get("ghost") is True

    def test_unknown_action_not_executed(self):
        """Unknown actions must NOT call _execute_action."""
        orch = AgentOrchestrator(max_steps=5)
        orch._execute_action = MagicMock()

        plan = {"action": "delete_everything", "params": {}, "reason": "test"}
        screen_state = {"path": "/tmp/test.png", "description": "test screen"}

        result = orch._act(plan, screen_state)

        orch._execute_action.assert_not_called()
        assert result.get("ghost") is True

    def test_force_ghost_action_not_executed(self):
        """force_ghost=True must block all actions."""
        orch = AgentOrchestrator(max_steps=5, force_ghost=True)
        orch._execute_action = MagicMock()

        # Even a safe click should be blocked with force_ghost
        plan = {"action": "click", "params": {"x": 100, "y": 200}, "reason": "test"}
        screen_state = {"path": "/tmp/test.png", "description": "test screen"}

        result = orch._act(plan, screen_state)

        orch._execute_action.assert_not_called()
        assert result.get("ghost") is True
