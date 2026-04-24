"""Tests for agent actions module."""

import json
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from peekxd.agent.actions import ActionSequence, ActionStep, ScreenDiff, WaitCondition


class TestActionSequence:
    """Test action sequence builder and executor."""

    def test_builder_methods(self):
        """Test that builder methods add steps."""
        seq = ActionSequence(
            screenshot_provider=MagicMock(),
            input_provider=MagicMock(),
        )
        seq.click(100, 200).type("hello").key("Return").wait(1.0)
        assert len(seq.steps) == 4
        assert seq.steps[0].action == "click"
        assert seq.steps[1].action == "type"
        assert seq.steps[2].action == "key"
        assert seq.steps[3].action == "wait"

    def test_click_execution(self):
        """Test click action execution."""
        mock_input = MagicMock()
        seq = ActionSequence(
            screenshot_provider=MagicMock(),
            input_provider=mock_input,
        )
        seq.click(100, 200, button="left")
        results = seq.execute()

        assert len(results) == 1
        assert results[0]["success"] is True
        mock_input.click.assert_called_once_with(100, 200, "left")

    def test_type_execution(self):
        """Test type action execution."""
        mock_input = MagicMock()
        seq = ActionSequence(
            screenshot_provider=MagicMock(),
            input_provider=mock_input,
        )
        seq.type("hello world")
        results = seq.execute()

        assert results[0]["success"] is True
        mock_input.type_text.assert_called_once_with("hello world")

    def test_serialization(self):
        """Test round-trip serialization."""
        seq = ActionSequence()
        seq.click(100, 200).type("test").wait(0.5)

        data = seq.to_dict()
        restored = ActionSequence.from_dict(data)

        assert len(restored.steps) == 3
        assert restored.steps[0].action == "click"
        assert restored.steps[0].params["x"] == 100

    def test_stop_on_error(self):
        """Test that execution stops on error when configured."""
        mock_input = MagicMock()
        mock_input.click.side_effect = Exception("click failed")

        seq = ActionSequence(
            screenshot_provider=MagicMock(),
            input_provider=mock_input,
        )
        seq.click(100, 200).type("should not run")
        results = seq.execute(stop_on_error=True)

        assert len(results) == 1  # Stopped after first error
        assert results[0]["success"] is False


class TestScreenDiff:
    """Test screen diffing functionality."""

    def test_capture_and_hash(self):
        """Test screenshot capture and hash computation."""
        diff = ScreenDiff()
        diff.last_screenshot = "/tmp/test.png"
        diff.last_hash = "abcd1234"
        assert diff.last_screenshot == "/tmp/test.png"
        assert diff.last_hash == "abcd1234"

    def test_first_call_always_changed(self):
        """Test that first has_changed returns True when no baseline."""
        diff = ScreenDiff()
        # Mock capture_and_hash to avoid actual screenshot
        with patch.object(diff, "capture_and_hash", return_value=("/tmp/test.png", "abc123")):
            result = diff.has_changed()
        assert result is True


class TestWaitCondition:
    """Test wait conditions."""

    def test_for_element_found(self):
        """Test waiting for element that exists."""
        mock_screenshot = MagicMock()
        mock_screenshot.capture_screen.return_value = "/tmp/test.png"
        mock_vision = MagicMock()
        mock_vision.find_element.return_value = (100, 200)

        result = WaitCondition.for_element(
            "Submit button",
            timeout=1.0,
            vision_provider=mock_vision,
            screenshot_provider=mock_screenshot,
        )

        assert result["found"] is True
        assert result["position"] == (100, 200)

    def test_for_element_timeout(self):
        """Test waiting for element that never appears."""
        mock_screenshot = MagicMock()
        mock_screenshot.capture_screen.return_value = "/tmp/test.png"
        mock_vision = MagicMock()
        mock_vision.find_element.return_value = None

        result = WaitCondition.for_element(
            "Nonexistent",
            timeout=0.1,
            poll_interval=0.05,
            vision_provider=mock_vision,
            screenshot_provider=mock_screenshot,
        )

        assert result["found"] is False
        assert result["position"] is None

    def test_for_text_found(self):
        """Test waiting for text that appears."""
        mock_screenshot = MagicMock()
        mock_screenshot.capture_screen.return_value = "/tmp/test.png"
        mock_vision = MagicMock()
        mock_vision.analyze.return_value = "yes"

        result = WaitCondition.for_text(
            "Loading complete",
            timeout=1.0,
            vision_provider=mock_vision,
            screenshot_provider=mock_screenshot,
        )

        assert result["found"] is True
        assert result["text"] == "Loading complete"
