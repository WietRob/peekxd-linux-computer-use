"""Tests for Softbox zone system (GHOST mode V1)."""

import pytest

from peekxd.core.zones import Zone, ZoneDecision, GhostPreviewResult, RiskDecision


class TestZoneEnum:
    """Test Zone enum values."""

    def test_zone_values(self):
        """Zone enum should have all four values."""
        assert Zone.GHOST.value == "ghost"
        assert Zone.SHADOW.value == "shadow"
        assert Zone.GUIDED.value == "guided"
        assert Zone.DIRECT.value == "direct"


class TestZoneDecision:
    """Test risk-based zone assignment."""

    def test_readonly_action_direct(self):
        """Non-pixel read-only actions should go to DIRECT."""
        decision = ZoneDecision.decide("see_semantic", {})
        assert decision.zone == Zone.DIRECT
        assert decision.risk_level == "safe"

    def test_click_safe_shadow(self):
        """Click on known coordinates should be SHADOW (V2: shadow snapshot)."""
        decision = ZoneDecision.decide("click", {"x": 100, "y": 200})
        assert decision.zone == Zone.SHADOW
        assert decision.risk_level == "safe"

    def test_rm_command_ghost(self):
        """Type with rm command should be GHOST."""
        decision = ZoneDecision.decide("type", {"text": "rm -rf /home"})
        assert decision.zone == Zone.GHOST
        assert decision.risk_level == "destructive"
        assert any("destructive" in f for f in decision.risk_factors)

    def test_sudo_command_ghost(self):
        """Type with sudo should be GHOST."""
        decision = ZoneDecision.decide("type", {"text": "sudo apt remove firefox"})
        assert decision.zone == Zone.GHOST
        assert "destructive" in decision.risk_factors[0]

    def test_dd_command_ghost(self):
        """Type with dd should be GHOST."""
        decision = ZoneDecision.decide("type", {"text": "dd if=/dev/zero of=/dev/sda"})
        assert decision.zone == Zone.GHOST

    def test_password_text_ghost(self):
        """Type with password should be GHOST (credential pattern)."""
        decision = ZoneDecision.decide("type", {"text": "password123"})
        assert decision.zone == Zone.GHOST
        assert any("credential" in f for f in decision.risk_factors)

    def test_api_key_text_ghost(self):
        """Type with api_key should be GHOST."""
        decision = ZoneDecision.decide("type", {"text": "api_key=sk-abc123"})
        assert decision.zone == Zone.GHOST

    def test_normal_text_shadow(self):
        """Normal typing should be SHADOW (V2: shadow snapshot)."""
        decision = ZoneDecision.decide("type", {"text": "Hello World"})
        assert decision.zone == Zone.SHADOW
        assert decision.risk_level == "safe"

    def test_scroll_direct(self):
        """Scroll should be DIRECT."""
        decision = ZoneDecision.decide("scroll", {"direction": "down"})
        assert decision.zone == Zone.DIRECT

    def test_unknown_action_ghost(self):
        """Unknown actions should default to GHOST (conservative)."""
        decision = ZoneDecision.decide("some_unknown_action", {})
        assert decision.zone == Zone.GHOST
        assert decision.risk_level == "warn"
        assert "unknown_action" in decision.risk_factors[0]

    def test_system_key_combo_ghost(self):
        """Ctrl+Alt+Delete should be GHOST."""
        decision = ZoneDecision.decide("key", {"hotkey": ["ctrl", "alt", "delete"]})
        assert decision.zone == Zone.GHOST
        assert any("system_key" in f for f in decision.risk_factors)

    def test_removed_capture_action_ghost(self):
        """Retired vision actions are blocked; real capture is allowed again."""
        decision = ZoneDecision.decide("analyze_screen", {})
        assert decision.zone == Zone.GHOST
        assert any("removed_screenshot_action" in f for f in decision.risk_factors)
        # G3: visible screenshot capture was restored by Owner decision.
        capture = ZoneDecision.decide("capture_screen", {"output_path": "shot.png"})
        assert capture.zone != Zone.GHOST

    def test_list_windows_direct(self):
        """List windows should be DIRECT."""
        decision = ZoneDecision.decide("list_windows", {})
        assert decision.zone == Zone.DIRECT

    def test_find_element_direct(self):
        """Find element should be DIRECT."""
        decision = ZoneDecision.decide("find_element", {"description": "Submit button"})
        assert decision.zone == Zone.DIRECT

    def test_ghost_preview_direct(self):
        """peekxd_ghost_preview should be DIRECT (read-only observation)."""
        decision = ZoneDecision.decide("peekxd_ghost_preview", {
            "action": "type_text",
            "params": {"text": "rm -rf /"},
        })
        assert decision.zone == Zone.DIRECT
        assert decision.risk_level == "safe"

    def test_preview_action_direct(self):
        """peekxd_preview_action should be DIRECT (read-only observation).

        This tool calls SafetyGuard.preview() without executing anything.
        It must be classified as read-only so the middleware does not
        GHOST-block it as an unknown action.
        """
        decision = ZoneDecision.decide("peekxd_preview_action", {
            "action": "type_text",
            "params": {"text": "rm -rf /"},
        })
        assert decision.zone == Zone.DIRECT
        assert decision.risk_level == "safe"
        assert decision.risk_factors == []

    def test_mark_elements_removed(self):
        """Mark-elements is pixel/vision capture and is blocked."""
        decision = ZoneDecision.decide("mark_elements", {})
        assert decision.zone == Zone.GHOST
        assert any("removed_screenshot_action" in f for f in decision.risk_factors)

    def test_multiple_risk_factors(self):
        """Multiple risk factors should all be recorded."""
        decision = ZoneDecision.decide(
            "type",
            {"text": "sudo rm -rf / && password=secret123"}
        )
        assert decision.zone == Zone.GHOST
        assert len(decision.risk_factors) >= 2


class TestGhostPreviewResult:
    """Test ghost preview generation."""

    def test_preview_structure(self):
        """Preview should have all required fields."""
        decision = ZoneDecision.decide("type", {"text": "rm -rf /"})
        preview = ZoneDecision.create_ghost_preview("type", {"text": "rm -rf /"}, decision)

        assert preview.action == "type"
        assert preview.zone == Zone.GHOST
        assert preview.requires_confirmation is True
        assert "destructive" in preview.risk_factors[0]

    def test_preview_dict(self):
        """Preview to_dict should be serializable."""
        decision = ZoneDecision.decide("click", {"x": 100, "y": 200, "text": "rm -rf /"})
        preview = ZoneDecision.create_ghost_preview("click", {"x": 100, "y": 200, "text": "rm -rf /"}, decision)
        d = preview.to_dict()

        assert d["action"] == "click"
        assert d["zone"] == "ghost"
        assert d["target_coordinates"] == (100, 200)
        assert d["requires_confirmation"] is True
        assert "params" in d

    def test_preview_masks_sensitive_params(self):
        """Preview should mask sensitive parameters."""
        preview = GhostPreviewResult(
            action="type",
            params={"text": "secretpassword", "username": "admin"},
            zone=Zone.GHOST,
        )
        d = preview.to_dict()
        # text should be masked
        assert d["params"]["text"] == "********"
        # username should not be masked
        assert d["params"]["username"] == "admin"

    def test_preview_text_preview_truncation(self):
        """Long text should be truncated in preview."""
        long_text = "a" * 100
        decision = ZoneDecision.decide("type", {"text": long_text})
        preview = ZoneDecision.create_ghost_preview("type", {"text": long_text}, decision)
        assert preview.text_preview == "a" * 50 + "..."

    def test_preview_short_text_no_truncation(self):
        """Short text should not be truncated."""
        decision = ZoneDecision.decide("type", {"text": "rm -rf /"})
        preview = ZoneDecision.create_ghost_preview("type", {"text": "rm -rf /"}, decision)
        assert preview.text_preview == "rm -rf /"


class TestRiskDecision:
    """Test RiskDecision dataclass."""

    def test_to_dict(self):
        """RiskDecision should serialize to dict."""
        decision = RiskDecision(
            zone=Zone.GHOST,
            risk_level="destructive",
            risk_factors=["pattern: rm"],
            reason="Destructive command detected",
        )
        d = decision.to_dict()
        assert d["zone"] == "ghost"
        assert d["risk_level"] == "destructive"
        assert d["risk_factors"] == ["pattern: rm"]
        assert d["reason"] == "Destructive command detected"
