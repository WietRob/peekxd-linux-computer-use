"""Tests for orchestrator zone integration (GHOST mode V1)."""

from unittest.mock import MagicMock, patch

import pytest

from peekxd.agent.orchestrator import AgentOrchestrator, TaskResult
from peekxd.core.safety import SafetyGuard, SafetyLevel
from peekxd.core.zones import Zone


class TestOrchestratorGhostMode:
    """Test that orchestrator correctly handles GHOST zone actions."""

    def test_ghost_action_not_executed(self):
        """GHOST zone action should NOT call _execute_action."""
        orch = AgentOrchestrator(max_steps=5)
        # Mock _execute_action to detect if it's called
        orch._execute_action = MagicMock(return_value={"success": True})

        plan = {"action": "type", "params": {"text": "rm -rf /"}, "reason": "test"}
        screen_state = {"path": "/tmp/test.png", "description": "test screen"}

        result = orch._act(plan, screen_state)

        # _execute_action should NOT have been called
        orch._execute_action.assert_not_called()
        # Result should indicate ghost blocking
        assert result.get("ghost") is True
        assert result.get("blocked") is True
        assert "GHOST" in result.get("detail", "")

    def test_direct_action_executed(self):
        """DIRECT zone action should execute normally."""
        orch = AgentOrchestrator(max_steps=5)
        orch._execute_action = MagicMock(return_value={"success": True, "detail": "clicked"})

        plan = {"action": "click", "params": {"x": 100, "y": 200}, "reason": "test"}
        screen_state = {"path": "/tmp/test.png", "description": "test screen"}

        result = orch._act(plan, screen_state)

        # _execute_action SHOULD have been called
        orch._execute_action.assert_called_once()
        assert result.get("success") is True
        assert result.get("ghost") is None

    def test_ghost_audit_logged(self):
        """GHOST action should create audit entry with executed=False."""
        orch = AgentOrchestrator(max_steps=5)
        orch._execute_action = MagicMock(return_value={"success": True})

        plan = {"action": "type", "params": {"text": "sudo apt remove firefox"}, "reason": "test"}
        screen_state = {"path": "/tmp/test.png", "description": "test screen"}

        orch._act(plan, screen_state)

        # Check audit log
        assert len(orch.audit.actions) == 1
        entry = orch.audit.actions[0]
        assert entry.action == "type"
        assert entry.result.get("zone") == "ghost"
        assert entry.result.get("executed") is False
        assert "ghost_preview" in entry.result

    def test_shadow_audit_logged_with_zone(self):
        """SHADOW action should create audit entry with zone=shadow and executed=True."""
        orch = AgentOrchestrator(max_steps=5)
        orch._execute_action = MagicMock(return_value={"success": True, "detail": "ok"})

        plan = {"action": "click", "params": {"x": 100, "y": 200}, "reason": "test"}
        screen_state = {"path": "/tmp/test.png", "description": "test screen"}

        orch._act(plan, screen_state)

        assert len(orch.audit.actions) == 1
        entry = orch.audit.actions[0]
        assert entry.action == "click"
        assert entry.result.get("zone") == "shadow"
        assert entry.result.get("executed") is True

    def test_safety_guard_has_zone_decisions(self):
        """G3: the canonical gate records the decision, not the legacy guard."""
        guard = SafetyGuard(SafetyLevel.NORMAL)

        # Trigger an action via orchestrator
        orch = AgentOrchestrator(max_steps=5, safety_level=SafetyLevel.NORMAL)
        orch.safety = guard
        orch._execute_action = MagicMock(return_value={"success": True})

        plan = {"action": "type", "params": {"text": "rm -rf /"}, "reason": "test"}
        screen_state = {"path": "/tmp/test.png", "description": "test screen"}

        result = orch._act(plan, screen_state)

        # G3: the legacy guard is no longer the execution authority.
        assert guard.get_zone_decisions() == []
        # The destructive action must be blocked by the gate (hard_blocked).
        assert result.get("blocked") is True or result.get("success") is False

    def test_done_action_not_zoned(self):
        """'done' action should bypass zone check."""
        orch = AgentOrchestrator(max_steps=5)
        orch._execute_action = MagicMock()

        plan = {"action": "done", "params": {}, "reason": "task complete"}
        screen_state = {"path": "/tmp/test.png", "description": "test screen"}

        result = orch._act(plan, screen_state)

        # _execute_action should not be called for done
        orch._execute_action.assert_not_called()
        assert result.get("done") is True
        assert result.get("success") is True

    def test_ghost_preview_contains_required_fields(self):
        """Ghost preview should contain all required information."""
        orch = AgentOrchestrator(max_steps=5)
        orch._execute_action = MagicMock()

        plan = {"action": "type", "params": {"text": "rm -rf /home/user"}, "reason": "test"}
        screen_state = {"path": "/tmp/test.png", "description": "test screen"}

        result = orch._act(plan, screen_state)

        preview = result.get("preview", {})
        assert preview["action"] == "type"
        assert preview["zone"] == "ghost"
        assert preview["requires_confirmation"] is True
        assert len(preview["risk_factors"]) > 0
        assert preview["reason"] != ""
        # Params should be masked
        assert "*" in preview["params"]["text"]

    def test_readonly_action_direct_zone(self):
        """Non-pixel read-only actions like list_windows should be DIRECT."""
        orch = AgentOrchestrator(max_steps=5)
        orch._execute_action = MagicMock(return_value={"success": True, "windows": []})

        plan = {"action": "list_windows", "params": {}, "reason": "observe"}
        screen_state = {"path": None, "description": "semantic screen"}

        result = orch._act(plan, screen_state)

        orch._execute_action.assert_called_once()
        assert result.get("success") is True
        # Audit should show direct zone
        assert orch.audit.actions[0].result.get("zone") == "direct"
