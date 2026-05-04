"""Tests for Softbox V4 Confirmable Ghost Actions.

Unit tests for the classification logic (ZoneDecision.classify_ghost_action).
These tests call classify_ghost_action() directly with explicit risk_factors,
bypassing the orchestrator flow entirely.

For orchestrator-level integration tests:
- test_orchestrator_confirmable_ghost.py — Mock-based GHOST-branch tests
- test_real_confirmable_ghost.py — Real ZoneDecision.decide() SHADOW-routing tests

Validates:
- GhostActionClassification enum
- GhostApprovalDecision dataclass
- ZoneDecision.classify_ghost_action() logic
- APPROVABLE_GHOST requires zero risk factors + known safe action type
- HARD_BLOCKED_GHOST for any risk factor, unknown action, or force_ghost
"""
import pytest
from unittest.mock import MagicMock, patch

from peekxd.core.zones import (
    GhostActionClassification,
    GhostApprovalDecision,
    ZoneDecision,
    Zone,
)


class TestGhostActionClassification:
    """Test the GhostActionClassification enum."""

    def test_enum_values(self):
        assert GhostActionClassification.HARD_BLOCKED_GHOST.value == "hard_blocked_ghost"
        assert GhostActionClassification.APPROVABLE_GHOST.value == "approvable_ghost"

    def test_enum_members(self):
        members = list(GhostActionClassification)
        assert len(members) == 2


class TestGhostApprovalDecision:
    """Test the GhostApprovalDecision dataclass."""

    def test_hard_blocked_decision(self):
        d = GhostApprovalDecision(
            classification=GhostActionClassification.HARD_BLOCKED_GHOST,
            can_execute_after_approval=False,
            hard_block_reason="destructive",
        )
        assert d.classification == GhostActionClassification.HARD_BLOCKED_GHOST
        assert d.can_execute_after_approval is False
        assert d.hard_block_reason == "destructive"
        assert d.approval_required is True

    def test_approvable_decision(self):
        d = GhostApprovalDecision(
            classification=GhostActionClassification.APPROVABLE_GHOST,
            can_execute_after_approval=True,
        )
        assert d.can_execute_after_approval is True
        assert d.hard_block_reason is None

    def test_to_dict(self):
        d = GhostApprovalDecision(
            classification=GhostActionClassification.APPROVABLE_GHOST,
            can_execute_after_approval=True,
        )
        result = d.to_dict()
        assert result["classification"] == "approvable_ghost"
        assert result["can_execute_after_approval"] is True
        assert result["hard_block_reason"] is None
        assert result["approval_required"] is True


class TestClassifyGhostAction:
    """Test ZoneDecision.classify_ghost_action()."""

    def test_force_ghost_always_hard_blocked(self):
        """force_ghost=True -> always HARD_BLOCKED, even for safe actions."""
        result = ZoneDecision.classify_ghost_action(
            action="click",
            params={"x": 100, "y": 200},
            risk_factors=[],
            force_ghost=True,
        )
        assert result.classification == GhostActionClassification.HARD_BLOCKED_GHOST
        assert result.can_execute_after_approval is False
        assert "force_ghost" in result.hard_block_reason

    def test_destructive_pattern_hard_blocked(self):
        """Destructive patterns -> always HARD_BLOCKED."""
        result = ZoneDecision.classify_ghost_action(
            action="type",
            params={"text": "rm -rf /"},
            risk_factors=["destructive_pattern: 'rm '"],
            force_ghost=False,
        )
        assert result.classification == GhostActionClassification.HARD_BLOCKED_GHOST
        assert result.can_execute_after_approval is False

    def test_credential_text_hard_blocked(self):
        """Credential patterns -> always HARD_BLOCKED."""
        result = ZoneDecision.classify_ghost_action(
            action="type",
            params={"text": "my_password=secret"},
            risk_factors=["credential_pattern: 'password'"],
            force_ghost=False,
        )
        assert result.classification == GhostActionClassification.HARD_BLOCKED_GHOST
        assert result.can_execute_after_approval is False

    def test_protected_path_hard_blocked(self):
        """Protected paths -> always HARD_BLOCKED."""
        result = ZoneDecision.classify_ghost_action(
            action="type",
            params={"output_path": "/etc/passwd"},
            risk_factors=["protected_path: /etc"],
            force_ghost=False,
        )
        assert result.classification == GhostActionClassification.HARD_BLOCKED_GHOST
        assert result.can_execute_after_approval is False

    def test_unknown_action_hard_blocked(self):
        """Unknown actions -> always HARD_BLOCKED."""
        result = ZoneDecision.classify_ghost_action(
            action="nuke_system",
            params={},
            risk_factors=[],
            force_ghost=False,
        )
        assert result.classification == GhostActionClassification.HARD_BLOCKED_GHOST
        assert "not in approvable" in result.hard_block_reason

    def test_normal_click_approvable(self):
        """Normal click with no risk factors -> APPROVABLE."""
        result = ZoneDecision.classify_ghost_action(
            action="click",
            params={"x": 100, "y": 200},
            risk_factors=[],
            force_ghost=False,
        )
        assert result.classification == GhostActionClassification.APPROVABLE_GHOST
        assert result.can_execute_after_approval is True
        assert result.hard_block_reason is None

    def test_normal_type_approvable(self):
        """Normal type with no risk factors -> APPROVABLE."""
        result = ZoneDecision.classify_ghost_action(
            action="type",
            params={"text": "hello world"},
            risk_factors=[],
            force_ghost=False,
        )
        assert result.classification == GhostActionClassification.APPROVABLE_GHOST
        assert result.can_execute_after_approval is True

    def test_type_text_approvable(self):
        """type_text with no risk factors -> APPROVABLE."""
        result = ZoneDecision.classify_ghost_action(
            action="type_text",
            params={"text": "hello"},
            risk_factors=[],
            force_ghost=False,
        )
        assert result.classification == GhostActionClassification.APPROVABLE_GHOST

    def test_hotkey_approvable(self):
        """hotkey with no risk factors -> APPROVABLE."""
        result = ZoneDecision.classify_ghost_action(
            action="hotkey",
            params={"hotkey": ["ctrl", "c"]},
            risk_factors=[],
            force_ghost=False,
        )
        assert result.classification == GhostActionClassification.APPROVABLE_GHOST

    def test_system_key_combo_hard_blocked(self):
        """System key combos -> HARD_BLOCKED via risk factors."""
        result = ZoneDecision.classify_ghost_action(
            action="hotkey",
            params={"hotkey": ["ctrl", "alt", "delete"]},
            risk_factors=["system_key_combo: ctrl+alt+delete"],
            force_ghost=False,
        )
        assert result.classification == GhostActionClassification.HARD_BLOCKED_GHOST

    def test_any_risk_factor_blocks(self):
        """Any single risk factor makes action HARD_BLOCKED."""
        result = ZoneDecision.classify_ghost_action(
            action="click",
            params={"x": 100, "y": 200},
            risk_factors=["some_random_risk"],
            force_ghost=False,
        )
        assert result.classification == GhostActionClassification.HARD_BLOCKED_GHOST

    def test_capture_screen_not_approvable(self):
        """Read-only actions like capture_screen are not in approvable set."""
        result = ZoneDecision.classify_ghost_action(
            action="capture_screen",
            params={},
            risk_factors=[],
            force_ghost=False,
        )
        assert result.classification == GhostActionClassification.HARD_BLOCKED_GHOST

    def test_sudo_in_text_hard_blocked(self):
        """sudo pattern -> HARD_BLOCKED."""
        result = ZoneDecision.classify_ghost_action(
            action="type",
            params={"text": "sudo apt install something"},
            risk_factors=["destructive_pattern: 'sudo '"],
            force_ghost=False,
        )
        assert result.classification == GhostActionClassification.HARD_BLOCKED_GHOST


class TestClassifyGhostActionIntegration:
    """Integration: classify using actual ZoneDecision.decide() risk factors."""

    def test_destructive_text_gets_risk_factors_and_blocks(self):
        """Full pipeline: destructive text -> GHOST zone -> HARD_BLOCKED."""
        decision = ZoneDecision.decide("type", {"text": "rm -rf /"})
        assert decision.zone == Zone.GHOST
        assert len(decision.risk_factors) > 0
        classification = ZoneDecision.classify_ghost_action(
            "type", {"text": "rm -rf /"}, decision.risk_factors, force_ghost=False,
        )
        assert classification.classification == GhostActionClassification.HARD_BLOCKED_GHOST

    def test_safe_type_gets_shadow_not_ghost(self):
        """Safe type -> SHADOW zone (not GHOST), so classify is never called for it."""
        decision = ZoneDecision.decide("type", {"text": "hello world"})
        assert decision.zone == Zone.SHADOW
