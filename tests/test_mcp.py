"""Tests for the MCP server."""

from unittest.mock import MagicMock, patch

import pytest

from peekxd.config import ConfigManager
from peekxd.mcp_server import create_mcp_server


class TestMCPServer:
    """Test suite for MCP server creation."""

    @pytest.fixture
    def config(self, tmp_path):
        """Provide a temporary ConfigManager."""
        return ConfigManager(str(tmp_path / "config.json"))

    def test_create_mcp_server_import_error(self):
        """Server creation raises ImportError when fastmcp is not installed."""
        with patch("peekxd.mcp_server.server.FastMCP", None):
            with pytest.raises(ImportError, match="fastmcp not installed"):
                create_mcp_server()

    def test_create_mcp_server_returns_instance(self, config):
        """create_mcp_server returns a FastMCP instance."""
        mock_mcp = MagicMock()
        mock_mcp.tool = MagicMock(return_value=lambda f: f)
        with patch("peekxd.mcp_server.server.FastMCP", return_value=mock_mcp):
            server = create_mcp_server(config)
            assert server is mock_mcp

    def _collect_tools(self, config):
        """Helper: create server and collect all registered tool functions."""
        registered = []

        def capture_tool(func):
            registered.append(func)
            return func

        mock_mcp = MagicMock()
        mock_mcp.tool = MagicMock(return_value=capture_tool)
        with patch("peekxd.mcp_server.server.FastMCP", return_value=mock_mcp):
            create_mcp_server(config)
        return registered, mock_mcp

    def test_tools_registered(self, config):
        """All expected tools are registered on the MCP server."""
        registered, _mock_mcp = self._collect_tools(config)
        tool_names = [f.__name__ for f in registered]

        expected_tools = [
            "see_semantic",
            "move_mouse",
            "click",
            "drag",
            "type_text",
            "scroll",
            "press_key",
            "list_windows",
            "focus_window",
            "get_ui_tree",
            "find_element",
            "get_active_window",
            "wait_for_element",
            "wait_for_text",
            "peekxd_set_safety_level",
            "peekxd_ghost_preview",
            "peekxd_audit_export",
            "peekxd_zone_check",
        ]
        for tool_name in expected_tools:
            assert tool_name in tool_names, f"Tool {tool_name} not registered"
        removed_tools = {
            "capture_screen",
            "mark_elements",
            "find_and_click",
            "type_into_field",
            "analyze_image",
            "screen_has_changed",
        }
        assert not removed_tools.intersection(tool_names)

    @patch("peekxd.mcp_server.server._get_window")
    @patch("peekxd.mcp_server.server._get_inspection")
    def test_see_semantic_tool_returns_snapshot_without_screenshot(
        self,
        mock_get_inspection,
        mock_get_window,
        config,
    ):
        """see_semantic returns the non-visual envelope."""
        from peekxd.inspection.base import UIElement

        inspection = MagicMock()
        inspection.get_ui_tree.return_value = [
            UIElement("raw", "Search", "button", (1, 2), (3, 4), None, [], {})
        ]
        mock_get_inspection.return_value = inspection
        window = MagicMock()
        window.list_windows.return_value = [
            {"id": "win", "title": "Browser", "class": "firefox"}
        ]
        mock_get_window.return_value = window

        registered, _ = self._collect_tools(config)
        see_semantic_func = [f for f in registered if f.__name__ == "see_semantic"][0]
        result = see_semantic_func(app_name="firefox")

        assert result["schema_version"] == "peekxd.see.v1"
        assert result["result"]["ok"] is True
        assert result["snapshot"]["elements"][0]["element_id"] == "W1-B1"
        assert result["zone"] == "direct"
        assert result["audit_id"]

    @patch("peekxd.mcp_server.server._get_input")
    def test_move_mouse(self, mock_get_input, config):
        """move_mouse tool delegates to input provider."""
        mock_provider = MagicMock()
        mock_get_input.return_value = mock_provider

        registered, _ = self._collect_tools(config)
        move_mouse_func = [f for f in registered if f.__name__ == "move_mouse"][0]
        result = move_mouse_func(x=100, y=200)
        assert result["success"] is True
        assert result["x"] == 100
        assert result["y"] == 200
        assert result["zone"] == "direct"
        assert result["audit_id"]
        mock_provider.move_mouse.assert_called_once_with(100, 200)

    @patch("peekxd.mcp_server.server._get_input")
    def test_click(self, mock_get_input, config):
        """click tool delegates to input provider."""
        mock_provider = MagicMock()
        mock_get_input.return_value = mock_provider

        registered, _ = self._collect_tools(config)
        click_func = [f for f in registered if f.__name__ == "click"][0]
        result = click_func(x=50, y=60, button="right")
        assert result["success"] is True
        assert result["button"] == "right"
        mock_provider.click.assert_called_once_with(50, 60, "right")

    @patch("peekxd.mcp_server.server._get_input")
    def test_type_text(self, mock_get_input, config):
        """type_text tool delegates to input provider."""
        mock_provider = MagicMock()
        mock_get_input.return_value = mock_provider

        registered, _ = self._collect_tools(config)
        type_text_func = [f for f in registered if f.__name__ == "type_text"][0]
        result = type_text_func(text="hello")
        assert result["success"] is True
        assert result["text"] == "hello"
        mock_provider.type_text.assert_called_once_with("hello")

    @patch("peekxd.mcp_server.server._get_input")
    def test_scroll(self, mock_get_input, config):
        """scroll tool delegates direction and amount to input provider."""
        mock_provider = MagicMock()
        mock_get_input.return_value = mock_provider

        registered, _ = self._collect_tools(config)
        scroll_func = [f for f in registered if f.__name__ == "scroll"][0]
        result = scroll_func(direction="up", amount=5)
        assert result["success"] is True
        assert result["direction"] == "up"
        assert result["amount"] == 5
        assert result["zone"] == "direct"
        assert result["audit_id"]
        mock_provider.scroll.assert_called_once_with("up", 5)

    @patch("peekxd.mcp_server.server._get_input")
    def test_press_key(self, mock_get_input, config):
        """press_key tool delegates to input provider."""
        mock_provider = MagicMock()
        mock_get_input.return_value = mock_provider

        registered, _ = self._collect_tools(config)
        press_key_func = [f for f in registered if f.__name__ == "press_key"][0]
        result = press_key_func(key="Return")
        assert result["success"] is True
        assert result["key"] == "Return"
        mock_provider.key_press.assert_called_once_with("Return")

    @patch("peekxd.mcp_server.server._get_window")
    def test_list_windows(self, mock_get_window, config):
        """list_windows tool returns window list."""
        mock_provider = MagicMock()
        mock_provider.list_windows.return_value = [
            {"id": "win1", "title": "Test Window"}
        ]
        mock_get_window.return_value = mock_provider

        registered, _ = self._collect_tools(config)
        list_windows_func = [f for f in registered if f.__name__ == "list_windows"][0]
        result = list_windows_func()
        assert result["result"] == [{"id": "win1", "title": "Test Window"}]
        assert result["zone"] == "direct"
        assert result["audit_id"]

    def test_safety_tools_registered_and_callable(self, config, tmp_path):
        """Safety helper tools expose level, preview, audit, and zone checks."""
        registered, _ = self._collect_tools(config)
        tools = {f.__name__: f for f in registered}

        level_result = tools["peekxd_set_safety_level"]("strict")
        assert level_result["success"] is True
        assert level_result["safety_level"] == "strict"
        assert level_result["audit_id"]

        preview_result = tools["peekxd_ghost_preview"](
            "type_text",
            {"text": "rm -rf /"},
        )
        assert preview_result["preview"]["zone"] == "ghost"
        assert preview_result["zone"] == "direct"

        zone_result = tools["peekxd_zone_check"]("type_text", {"text": "rm -rf /"})
        assert zone_result["decision"]["zone"] == "ghost"
        assert zone_result["audit_id"]

        export_path = tmp_path / "audit.json"
        export_result = tools["peekxd_audit_export"](str(export_path))
        assert export_result["success"] is True
        assert export_path.exists()

    @patch("peekxd.mcp_server.server._get_window")
    def test_focus_window(self, mock_get_window, config):
        """focus_window tool focuses a window."""
        mock_provider = MagicMock()
        mock_get_window.return_value = mock_provider

        registered, _ = self._collect_tools(config)
        focus_window_func = [f for f in registered if f.__name__ == "focus_window"][0]
        result = focus_window_func(window_id="0x01")
        assert result["success"] is True
        assert result["window_id"] == "0x01"
        mock_provider.focus_window.assert_called_once_with("0x01")
