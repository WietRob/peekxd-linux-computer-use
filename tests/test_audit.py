"""Tests for audit logger."""

import json
import tempfile

import pytest

from peekxd.core.audit import AuditLogger, ActionEntry, get_logger, reset_logger


class TestAuditLogger:
    """Test audit logging."""

    def test_log_action(self):
        """Should log an action with all fields."""
        logger = AuditLogger()
        entry = logger.log_action("click", {"x": 100, "y": 200}, {"success": True})

        assert entry.action == "click"
        assert entry.params == {"x": 100, "y": 200}
        assert entry.result == {"success": True}
        assert entry.step == 0
        assert entry.error is None

    def test_multiple_actions_increment_step(self):
        """Steps should auto-increment."""
        logger = AuditLogger()
        e1 = logger.log_action("click", {"x": 0, "y": 0})
        e2 = logger.log_action("type", {"text": "hi"})

        assert e1.step == 0
        assert e2.step == 1

    def test_log_error(self):
        """Should log errors."""
        logger = AuditLogger()
        entry = logger.log_action("click", {"x": 0, "y": 0}, error="Timeout")

        assert entry.error == "Timeout"

    def test_session_summary(self):
        """Summary should contain key metrics."""
        logger = AuditLogger()
        logger.log_action("click", {}, {"success": True})
        logger.log_action("type", {}, {"success": True})
        logger.log_action("click", {}, {"success": False}, error="fail")

        summary = logger.get_session_summary()
        assert summary["total_actions"] == 3
        assert summary["successful"] == 2
        assert summary["failed"] == 1
        assert summary["session_id"]

    def test_export_json(self):
        """Should export to valid JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = AuditLogger()
            logger.log_action("click", {"x": 100, "y": 200})

            path = logger.export_json(f"{tmpdir}/audit.json")
            assert path == f"{tmpdir}/audit.json"
            assert open(path).read().startswith("{")

            data = json.load(open(path))
            assert data["session_id"] == logger.session_id
            assert data["total_actions"] == 1

    def test_recent_actions(self):
        """Should return N most recent actions."""
        logger = AuditLogger()
        for i in range(5):
            logger.log_action("click", {"x": i, "y": i})

        recent = logger.recent_actions(3)
        assert len(recent) == 3
        assert recent[-1].params["x"] == 4

    def test_find_actions(self):
        """Should filter by action type."""
        logger = AuditLogger()
        logger.log_action("click", {})
        logger.log_action("type", {})
        logger.log_action("click", {})

        clicks = logger.find_actions("click")
        assert len(clicks) == 2

    def test_screenshot_counter(self):
        """Screenshot counter should increment."""
        logger = AuditLogger()
        p1 = logger.get_next_screenshot_path()
        p2 = logger.get_next_screenshot_path()

        assert "_0001" in p1
        assert "_0002" in p2

    def test_format_readable(self):
        """Readable format should contain action info."""
        logger = AuditLogger()
        logger.log_action("click", {"x": 100, "y": 200}, {"success": True})

        text = logger.format_readable()
        assert "click" in text
        assert "OK" in text

    def test_global_logger(self):
        """Global logger singleton."""
        reset_logger()
        l1 = get_logger()
        l2 = get_logger()
        assert l1 is l2
        reset_logger()
