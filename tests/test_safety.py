"""Tests for safety guardrails."""

import pytest

from peekxd.core.safety import SafetyGuard, SafetyLevel, DryRunExecutor, PermissionDeniedError


class TestSafetyGuard:
    """Test safety guardrail system."""

    def test_permissive_allows_all(self):
        """Permissive mode should allow everything."""
        guard = SafetyGuard(SafetyLevel.PERMISSIVE)
        assert guard.check_action("type", {"text": "rm -rf /"}) is True

    def test_strict_blocks_destructive(self):
        """Strict mode should block destructive commands."""
        guard = SafetyGuard(SafetyLevel.STRICT)
        with pytest.raises(PermissionDeniedError):
            guard.check_action("type", {"text": "rm -rf /home"})

    def test_normal_allows_with_warning(self):
        """Normal mode should allow but log."""
        guard = SafetyGuard(SafetyLevel.NORMAL)
        result = guard.check_action("type", {"text": "rm file.txt"})
        assert result is True
        assert len(guard.get_log()) == 1

    def test_safe_text_allowed(self):
        """Normal text should pass."""
        guard = SafetyGuard(SafetyLevel.STRICT)
        assert guard.check_action("type", {"text": "Hello World"}) is True

    def test_sudo_blocked(self):
        """Sudo commands should be flagged."""
        guard = SafetyGuard(SafetyLevel.STRICT)
        with pytest.raises(PermissionDeniedError):
            guard.check_action("type", {"text": "sudo apt remove firefox"})

    def test_dd_blocked(self):
        """dd commands should be flagged."""
        guard = SafetyGuard(SafetyLevel.STRICT)
        with pytest.raises(PermissionDeniedError):
            guard.check_action("type", {"text": "dd if=/dev/zero of=/dev/sda"})

    def test_click_is_safe(self):
        """Click actions should be safe."""
        guard = SafetyGuard(SafetyLevel.STRICT)
        assert guard.check_action("click", {"x": 100, "y": 200}) is True

    def test_key_combinations(self):
        """System key combos should be warned."""
        guard = SafetyGuard(SafetyLevel.NORMAL)
        assert guard.check_action("key", {"hotkey": ["ctrl", "alt", "delete"]}) is True
        log = guard.get_log()
        assert len(log) == 1
        assert log[0]["risk"] == "warn"

    def test_preview_mode(self):
        """Preview should not execute."""
        guard = SafetyGuard(SafetyLevel.STRICT)
        result = guard.preview("click", {"x": 100, "y": 200})
        assert result["preview"] is True
        assert result["action"] == "click"

    def test_reset_log(self):
        """Log should be resettable."""
        guard = SafetyGuard(SafetyLevel.NORMAL)
        guard.check_action("type", {"text": "rm test"})
        assert len(guard.get_log()) == 1
        guard.reset_log()
        assert len(guard.get_log()) == 0


class TestDryRunExecutor:
    """Test dry-run executor."""

    def test_logs_actions(self):
        """Dry-run should log actions without executing."""
        dry = DryRunExecutor()
        result = dry.execute("click", {"x": 100, "y": 200})

        assert result["dry_run"] is True
        assert len(dry.get_plan()) == 1

    def test_summary(self):
        """Summary should list all logged actions."""
        dry = DryRunExecutor()
        dry.execute("click", {"x": 100, "y": 200})
        dry.execute("type", {"text": "hello"})

        summary = dry.summary()
        assert "2 steps" in summary or "steps" in summary
        assert "click" in summary
        assert "type" in summary

    def test_no_real_execution(self):
        """Dry-run should never call real executor."""
        real = lambda **kwargs: pytest.fail("Real executor should not be called")
        dry = DryRunExecutor(real_executor=real)
        result = dry.execute("click", {"x": 100, "y": 200})
        assert result["dry_run"] is True
