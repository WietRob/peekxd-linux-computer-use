"""Tests for Hermes tools module."""

import json
from unittest.mock import MagicMock, patch

import pytest

from peekxd.agent.hermes_tools import (
    get_hermes_tool_definitions,
    execute_hermes_action,
    HERMES_TOOLS,
)


class TestToolDefinitions:
    """Test Hermes tool schema definitions."""

    def test_definitions_is_list(self):
        """Tool definitions should be a list."""
        tools = get_hermes_tool_definitions()
        assert isinstance(tools, list)
        assert len(tools) > 0

    def test_each_tool_has_required_fields(self):
        """Each tool must have name, description, parameters."""
        tools = get_hermes_tool_definitions()
        for tool in tools:
            assert "name" in tool
            assert "description" in tool
            assert "parameters" in tool
            assert "type" in tool["parameters"]
            assert tool["parameters"]["type"] == "object"

    def test_known_tools_exist(self):
        """Verify all expected tools are defined."""
        tools = get_hermes_tool_definitions()
        names = {t["name"] for t in tools}
        expected = {
            "peekxd_capture_screen",
            "peekxd_analyze_screen",
            "peekxd_find_element",
            "peekxd_click",
            "peekxd_type",
            "peekxd_key",
            "peekxd_move_mouse",
            "peekxd_scroll",
            "peekxd_list_windows",
            "peekxd_focus_window",
            "peekxd_inspect_ui",
            "peekxd_wait",
            "peekxd_run_sequence",
            "peekxd_mark_elements",
            "peekxd_drag",
        }
        for exp in expected:
            assert exp in names, f"Missing tool: {exp}"


class TestActionExecution:
    """Test Hermes action execution by patching the dispatch layer."""

    def test_unknown_tool(self):
        """Unknown tool should return error."""
        result = execute_hermes_action("peekxd_nonexistent", {})
        assert result["success"] is False
        assert "Unknown tool" in result["error"]

    def test_click_with_coordinates(self):
        """Test click at coordinates."""
        mock_input = MagicMock()
        with patch("peekxd.agent.hermes_tools._get_input", return_value=mock_input):
            with patch("peekxd.agent.hermes_tools._get_screenshot", return_value=MagicMock()):
                result = execute_hermes_action("peekxd_click", {"x": 100, "y": 200, "button": "left"})

        assert result["success"] is True
        assert result["result"]["clicked"] is True

    def test_type(self):
        """Test type action."""
        mock_input = MagicMock()
        with patch("peekxd.agent.hermes_tools._get_input", return_value=mock_input):
            result = execute_hermes_action("peekxd_type", {"text": "hello"})

        assert result["success"] is True
        mock_input.type_text.assert_called_once_with("hello")

    def test_list_windows(self):
        """Test list windows."""
        mock_window = MagicMock()
        mock_window.list_windows.return_value = [
            {"id": "123", "title": "Firefox", "class": "firefox"}
        ]
        with patch("peekxd.agent.hermes_tools._get_window", return_value=mock_window):
            result = execute_hermes_action("peekxd_list_windows", {})

        assert result["success"] is True
        assert len(result["result"]) == 1

    def test_capture_screen(self):
        """Test screen capture."""
        mock_screenshot = MagicMock()
        mock_screenshot.capture_screen.return_value = "/tmp/cap.png"
        with patch("peekxd.agent.hermes_tools._get_screenshot", return_value=mock_screenshot):
            result = execute_hermes_action("peekxd_capture_screen", {"mode": "screen"})

        assert result["success"] is True
        assert result["result"]["mode"] == "screen"

    def test_key_press(self):
        """Test key press."""
        mock_input = MagicMock()
        with patch("peekxd.agent.hermes_tools._get_input", return_value=mock_input):
            result = execute_hermes_action("peekxd_key", {"key": "Return"})

        assert result["success"] is True
        mock_input.key_press.assert_called_once_with("Return")

    def test_hotkey(self):
        """Test hotkey combination."""
        mock_input = MagicMock()
        with patch("peekxd.agent.hermes_tools._get_input", return_value=mock_input):
            result = execute_hermes_action("peekxd_key", {"hotkey": ["ctrl", "c"]})

        assert result["success"] is True
        mock_input.hotkey.assert_called_once_with("ctrl", "c")

    def test_drag(self):
        """Test drag action with coordinates."""
        mock_input = MagicMock()
        with patch("peekxd.agent.hermes_tools._get_input", return_value=mock_input):
            result = execute_hermes_action("peekxd_drag", {
                "x1": 100, "y1": 200, "x2": 300, "y2": 400,
            })

        assert result["success"] is True
        assert result["result"]["dragged"] is True
        assert result["result"]["from_x"] == 100
        assert result["result"]["from_y"] == 200
        assert result["result"]["to_x"] == 300
        assert result["result"]["to_y"] == 400
        mock_input.drag.assert_called_once_with(100, 200, 300, 400)
