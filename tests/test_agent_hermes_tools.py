"""Tests for Hermes tools module."""

import json
from unittest.mock import MagicMock, patch

from peekxd.agent.hermes_tools import get_hermes_tool_definitions, execute_hermes_action


def _result(action, params):
    return json.loads(execute_hermes_action(action, params))


class TestToolDefinitions:
    def test_definitions_is_list(self):
        tools = get_hermes_tool_definitions()
        assert isinstance(tools, list)
        assert len(tools) > 0

    def test_each_tool_has_required_fields(self):
        for tool in get_hermes_tool_definitions():
            assert "name" in tool
            assert "description" in tool
            assert "parameters" in tool
            assert tool["parameters"]["type"] == "object"

    def test_semantic_safe_tools_exist_and_screenshot_tools_removed(self):
        names = {t["name"] for t in get_hermes_tool_definitions()}
        expected = {
            "peekxd_see_semantic",
            "peekxd_click",
            "peekxd_type",
            "peekxd_key",
            "peekxd_move_mouse",
            "peekxd_scroll",
            "peekxd_list_windows",
            "peekxd_focus_window",
            "peekxd_inspect_ui",
        }
        assert expected.issubset(names)
        removed = {
            "peekxd_capture_screen",
            "peekxd_analyze_screen",
            "peekxd_find_element",
            "peekxd_wait",
            "peekxd_run_sequence",
            "peekxd_mark_elements",
        }
        assert names.isdisjoint(removed)


class TestActionExecution:
    def test_unknown_removed_tool(self):
        result = _result("peekxd_capture_screen", {"mode": "screen"})
        assert result["success"] is False
        assert "Unknown or removed" in result["error"]

    def test_click_with_coordinates(self):
        mock_input = MagicMock()
        with patch("peekxd.agent.hermes_tools._get_input", return_value=mock_input):
            result = _result("peekxd_click", {"x": 100, "y": 200, "button": "left"})

        assert result["success"] is True
        assert result["action"] == "click"
        mock_input.click.assert_called_once_with(100, 200, "left")

    def test_type(self):
        mock_input = MagicMock()
        with patch("peekxd.agent.hermes_tools._get_input", return_value=mock_input):
            result = _result("peekxd_type", {"text": "hello"})

        assert result["success"] is True
        mock_input.type_text.assert_called_once_with("hello")

    def test_list_windows(self):
        mock_window = MagicMock()
        mock_window.list_windows.return_value = [{"id": "123", "title": "Firefox", "class": "firefox"}]
        with patch("peekxd.agent.hermes_tools._get_window", return_value=mock_window):
            result = _result("peekxd_list_windows", {})

        assert result["success"] is True
        assert len(result["windows"]) == 1

    def test_key_press(self):
        mock_input = MagicMock()
        with patch("peekxd.agent.hermes_tools._get_input", return_value=mock_input):
            result = _result("peekxd_key", {"key": "Return"})

        assert result["success"] is True
        mock_input.key_press.assert_called_once_with("Return")

    def test_hotkey(self):
        mock_input = MagicMock()
        with patch("peekxd.agent.hermes_tools._get_input", return_value=mock_input):
            result = _result("peekxd_key", {"hotkey": ["ctrl", "c"]})

        assert result["success"] is True
        mock_input.hotkey.assert_called_once_with("ctrl", "c")
