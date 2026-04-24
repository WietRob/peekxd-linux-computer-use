"""Tests for ShadowRecorder (Softbox Shadow Mode V2)."""

import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from peekxd.core.shadow import ShadowRecorder, ShadowSnapshot, ShadowResult


class TestShadowSnapshot:
    """Test ShadowSnapshot dataclass."""

    def test_snapshot_structure(self):
        """Snapshot should have timestamp, path, metadata."""
        snap = ShadowSnapshot(
            timestamp="12345.0",
            screenshot_path="/tmp/test.png",
            metadata={"source": "screen_state"},
        )
        assert snap.timestamp == "12345.0"
        assert snap.screenshot_path == "/tmp/test.png"
        assert snap.metadata == {"source": "screen_state"}

    def test_snapshot_to_dict(self):
        """to_dict should serialize correctly."""
        snap = ShadowSnapshot(
            timestamp="12345.0",
            screenshot_path="/tmp/test.png",
            metadata={"source": "test"},
        )
        d = snap.to_dict()
        assert d["timestamp"] == "12345.0"
        assert d["screenshot_path"] == "/tmp/test.png"
        assert d["metadata"] == {"source": "test"}

    def test_snapshot_none_path(self):
        """Snapshot with None path is valid."""
        snap = ShadowSnapshot(timestamp="12345.0", screenshot_path=None)
        assert snap.screenshot_path is None
        d = snap.to_dict()
        assert d["screenshot_path"] is None


class TestShadowRecorder:
    """Test ShadowRecorder core behavior."""

    def test_snapshot_before_from_screen_state(self):
        """Should create before snapshot from screen_state path (test 1)."""
        recorder = ShadowRecorder()
        screen_state = {"path": "/tmp/current.png", "description": "test"}
        snap = recorder.snapshot_before(screen_state)
        assert snap is not None
        assert snap.screenshot_path == "/tmp/current.png"
        assert snap.metadata["source"] == "screen_state"

    def test_snapshot_before_no_screen_state(self):
        """Should survive missing screen_state (test 2)."""
        recorder = ShadowRecorder()
        snap = recorder.snapshot_before(None)
        assert snap is None

    def test_snapshot_before_empty_screen_state(self):
        """Should survive empty screen_state."""
        recorder = ShadowRecorder()
        snap = recorder.snapshot_before({})
        assert snap is None

    def test_snapshot_before_fresh_capture(self):
        """Should capture fresh screenshot if screen_state has no path."""
        capture_called = []

        def fake_capture(path):
            capture_called.append(path)

        def fake_get_path():
            return "/tmp/fresh_001.png"

        recorder = ShadowRecorder(capture_fn=fake_capture, get_screenshot_path_fn=fake_get_path)
        snap = recorder.snapshot_before({})
        assert snap is not None
        assert snap.screenshot_path == "/tmp/fresh_001.png"
        assert snap.metadata["source"] == "fresh_capture"
        assert len(capture_called) == 1

    def test_snapshot_after_fresh_capture(self):
        """After snapshot should always capture fresh."""
        capture_called = []

        def fake_capture(path):
            capture_called.append(path)

        def fake_get_path():
            return "/tmp/fresh_002.png"

        recorder = ShadowRecorder(capture_fn=fake_capture, get_screenshot_path_fn=fake_get_path)
        snap = recorder.snapshot_after({"path": "/tmp/old.png"})
        assert snap is not None
        assert snap.screenshot_path == "/tmp/fresh_002.png"
        assert snap.metadata["source"] == "fresh_capture"

    def test_snapshot_after_fails_with_exception(self):
        """After snapshot failure should raise exception (caught by wrap)."""
        def fail_capture(path):
            raise RuntimeError("Screenshot failed")

        recorder = ShadowRecorder(capture_fn=fail_capture, get_screenshot_path_fn=lambda: "/tmp/x.png")
        with pytest.raises(RuntimeError, match="Screenshot failed"):
            recorder.snapshot_after(None)


class TestShadowCompare:
    """Test ShadowRecorder.compare."""

    def test_compare_none_both(self):
        """Both None → changed=None."""
        recorder = ShadowRecorder()
        result = recorder.compare(None, None)
        assert result.changed is None
        assert "No snapshots" in result.diff_summary

    def test_compare_none_before(self):
        """Before None → changed=None."""
        after = ShadowSnapshot(timestamp="1", screenshot_path="/tmp/a.png")
        recorder = ShadowRecorder()
        result = recorder.compare(None, after)
        assert result.changed is None
        assert "No before snapshot" in result.diff_summary

    def test_compare_none_after(self):
        """After None → changed=None."""
        before = ShadowSnapshot(timestamp="1", screenshot_path="/tmp/a.png")
        recorder = ShadowRecorder()
        result = recorder.compare(before, None)
        assert result.changed is None
        assert "No after snapshot" in result.diff_summary

    def test_compare_identical_files(self):
        """Identical files → changed=False (test 3)."""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"identical content")
            tmp1 = f.name
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as g:
            g.write(b"identical content")
            tmp2 = g.name

        try:
            before = ShadowSnapshot(timestamp="1", screenshot_path=tmp1)
            after = ShadowSnapshot(timestamp="2", screenshot_path=tmp2)
            recorder = ShadowRecorder()
            result = recorder.compare(before, after)
            assert result.changed is False
            assert "identical" in result.diff_summary.lower()
        finally:
            os.unlink(tmp1)
            os.unlink(tmp2)

    def test_compare_different_files(self):
        """Different files → changed=True (test 4)."""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"before content")
            tmp1 = f.name
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as g:
            g.write(b"after content - different")
            tmp2 = g.name

        try:
            before = ShadowSnapshot(timestamp="1", screenshot_path=tmp1)
            after = ShadowSnapshot(timestamp="2", screenshot_path=tmp2)
            recorder = ShadowRecorder()
            result = recorder.compare(before, after)
            assert result.changed is True
            assert "differ" in result.diff_summary.lower()
        finally:
            os.unlink(tmp1)
            os.unlink(tmp2)

    def test_compare_missing_file(self):
        """Missing file → changed=None with error."""
        before = ShadowSnapshot(timestamp="1", screenshot_path="/tmp/nonexistent.png")
        after = ShadowSnapshot(timestamp="2", screenshot_path="/tmp/also_nonexistent.png")
        recorder = ShadowRecorder()
        result = recorder.compare(before, after)
        assert result.changed is None
        assert result.error is not None


class TestShadowWrap:
    """Test ShadowRecorder.wrap."""

    def test_wrap_calls_action_once(self):
        """wrap should call action_callable exactly once (test 5)."""
        call_count = [0]

        def action():
            call_count[0] += 1
            return {"success": True}

        recorder = ShadowRecorder()
        result, shadow = recorder.wrap(
            action_callable=action,
            action="click",
            params={"x": 100},
            screen_state={"path": "/tmp/test.png"},
        )

        assert call_count[0] == 1
        assert result == {"success": True}

    def test_wrap_returns_unchanged_result(self):
        """wrap should return action_result unchanged + ShadowResult (test 6)."""
        expected = {"success": True, "detail": "typed 'hello'", "x": 100}

        recorder = ShadowRecorder()
        result, shadow = recorder.wrap(
            action_callable=lambda: expected,
            action="type",
            params={"text": "hello"},
            screen_state={"path": "/tmp/test.png"},
        )

        assert result == expected
        assert isinstance(shadow, ShadowResult)
        assert shadow.before_snapshot is not None
        assert shadow.before_snapshot.screenshot_path == "/tmp/test.png"

    def test_wrap_action_called_even_if_snapshot_fails(self):
        """Action should execute even if before snapshot fails."""
        call_count = [0]

        def action():
            call_count[0] += 1
            return {"success": True}

        recorder = ShadowRecorder()
        result, shadow = recorder.wrap(
            action_callable=action,
            action="type",
            params={"text": "hello"},
            screen_state=None,  # No screen state → before snapshot is None
        )

        assert call_count[0] == 1
        assert result == {"success": True}

    def test_wrap_snapshot_error_in_shadow_result(self):
        """Snapshot errors should be in shadow_result.error."""
        call_count = [0]

        def action():
            call_count[0] += 1
            return {"success": True}

        # Create a recorder where after-snapshot always fails
        def fail_capture(path):
            raise RuntimeError("Screenshot failed")

        recorder = ShadowRecorder(
            capture_fn=fail_capture,
            get_screenshot_path_fn=lambda: "/tmp/x.png",
        )
        result, shadow = recorder.wrap(
            action_callable=action,
            action="click",
            params={"x": 100},
            screen_state={"path": "/tmp/before.png"},
        )

        assert call_count[0] == 1  # Action still executed
        assert result == {"success": True}  # Result preserved
        assert shadow.error is not None  # Error captured
        assert "After snapshot failed" in shadow.error

    def test_wrap_shadow_dict_serializable(self):
        """ShadowResult.to_dict should be JSON-serializable."""
        import json
        recorder = ShadowRecorder()
        _, shadow = recorder.wrap(
            action_callable=lambda: {"ok": True},
            action="type",
            params={"text": "hello"},
            screen_state={"path": "/tmp/test.png"},
        )
        d = shadow.to_dict()
        assert isinstance(d, dict)
        assert "snapshot_before" in d
        assert "snapshot_after" in d
        assert "changed" in d
        assert "diff_summary" in d
        # Should be serializable
        json.dumps(d)
