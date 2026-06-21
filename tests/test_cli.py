"""Tests for the peekxd CLI."""

import json
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from peekxd.cli import cli, main


def _setup_mock_module(name: str, provider: MagicMock):
    """Create a mock submodule with a get_*_provider function."""
    mod = ModuleType(name)
    mod.__file__ = f"<mock {name}>"
    func_name = name.split(".")[-1]
    setattr(mod, f"get_{func_name}_provider", lambda: provider)
    sys.modules[name] = mod
    return mod


@pytest.fixture(autouse=True)
def mock_submodules():
    """Provide mock submodules so CLI local imports succeed."""
    modules_to_remove = []
    # Store originals if they exist
    original_modules = {}

    # Create mock providers
    mock_providers = {
        "peekxd.input": MagicMock(),
        "peekxd.screenshot": MagicMock(),
        "peekxd.window": MagicMock(),
        "peekxd.inspection": MagicMock(),
        "peekxd.vision": MagicMock(),
    }

    for name, provider in mock_providers.items():
        if name in sys.modules:
            original_modules[name] = sys.modules[name]
        _setup_mock_module(name, provider)
        modules_to_remove.append(name)

    yield mock_providers

    # Cleanup
    for name in modules_to_remove:
        if name in sys.modules:
            del sys.modules[name]
    for name, mod in original_modules.items():
        sys.modules[name] = mod


class TestCLI:
    """Test suite for CLI commands."""

    @pytest.fixture
    def runner(self):
        """Provide a Click CLI test runner."""
        return CliRunner()

    def test_cli_help(self, runner):
        """CLI shows help text."""
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "peekxd" in result.output
        assert "Linux automation" in result.output

    def test_version(self, runner):
        """version command shows version string."""
        result = runner.invoke(cli, ["version"])
        assert result.exit_code == 0
        assert "0.3.0" in result.output

    def test_config_show(self, runner):
        """config show displays current configuration."""
        with runner.isolated_filesystem():
            result = runner.invoke(cli, ["config", "show"])
            assert result.exit_code == 0
            assert "screenshot" in result.output
            assert "vision" in result.output

    def test_config_init(self, runner):
        """config init creates a config file."""
        with runner.isolated_filesystem():
            result = runner.invoke(cli, ["config", "init"])
            assert result.exit_code == 0
            assert "Config created" in result.output

    def test_config_set_and_get(self, runner):
        """config set writes a value and config get reads it back."""
        with runner.isolated_filesystem():
            result = runner.invoke(cli, ["config", "set", "screenshot.format", "jpg"])
            assert result.exit_code == 0
            assert "Set screenshot.format = jpg" in result.output

            result = runner.invoke(cli, ["config", "get", "screenshot.format"])
            assert result.exit_code == 0
            assert "jpg" in result.output

    def test_click_command(self, mock_submodules, runner):
        """click command invokes the input provider."""
        provider = mock_submodules["peekxd.input"]
        result = runner.invoke(cli, ["click", "100", "200", "--button", "left"])
        assert result.exit_code == 0
        assert "Clicked left at 100,200" in result.output
        provider.click.assert_called_once_with(100, 200, "left")

    def test_type_command(self, mock_submodules, runner):
        """type command invokes the input provider."""
        provider = mock_submodules["peekxd.input"]
        result = runner.invoke(cli, ["type", "hello world"])
        assert result.exit_code == 0
        assert "Typed: hello world" in result.output
        provider.type_text.assert_called_once_with("hello world")

    def test_click_on_element_uses_semantic_bbox_center(self, mock_submodules, runner):
        """click --on resolves an element id and clicks its bbox center."""
        from peekxd.inspection.base import UIElement

        input_provider = mock_submodules["peekxd.input"]
        mock_submodules["peekxd.inspection"].get_ui_tree.return_value = [
            UIElement("raw-button", "Submit", "button", (10, 20), (30, 40), None, [], {})
        ]

        result = runner.invoke(cli, ["click", "--on", "W1-B1", "--button", "right"])

        assert result.exit_code == 0, result.output
        assert "Clicked right on W1-B1 at 25,40" in result.output
        input_provider.click.assert_called_once_with(25, 40, "right")

    def test_type_on_element_clicks_semantic_bbox_center_then_types(self, mock_submodules, runner):
        """type --on resolves an element id, focuses it, then types text."""
        from peekxd.inspection.base import UIElement

        input_provider = mock_submodules["peekxd.input"]
        mock_submodules["peekxd.inspection"].get_ui_tree.return_value = [
            UIElement("raw-text", "Search", "text", (5, 6), (100, 20), None, [], {})
        ]

        result = runner.invoke(cli, ["type", "hello world", "--on", "W1-T1"])

        assert result.exit_code == 0, result.output
        assert "Typed into W1-T1 at 55,16: hello world" in result.output
        input_provider.click.assert_called_once_with(55, 16, "left")
        input_provider.type_text.assert_called_once_with("hello world")

    def test_key_command(self, mock_submodules, runner):
        """key command invokes the input provider."""
        provider = mock_submodules["peekxd.input"]
        result = runner.invoke(cli, ["key", "Return"])
        assert result.exit_code == 0
        assert "Key: Return" in result.output
        provider.key_press.assert_called_once_with("Return")

    def test_key_hotkey(self, mock_submodules, runner):
        """key command with --hotkey splits on comma."""
        provider = mock_submodules["peekxd.input"]
        result = runner.invoke(cli, ["key", "ctrl,c", "--hotkey"])
        assert result.exit_code == 0
        assert "Hotkey: ctrl+c" in result.output
        provider.hotkey.assert_called_once_with("ctrl", "c")

    def test_move_command(self, mock_submodules, runner):
        """move command invokes the input provider."""
        provider = mock_submodules["peekxd.input"]
        result = runner.invoke(cli, ["move", "300", "400"])
        assert result.exit_code == 0
        assert "Moved to 300,400" in result.output
        provider.move_mouse.assert_called_once_with(300, 400)

    def test_scroll_command(self, mock_submodules, runner):
        """scroll command invokes the input provider."""
        provider = mock_submodules["peekxd.input"]
        result = runner.invoke(cli, ["scroll", "--direction", "up", "--amount", "5"])
        assert result.exit_code == 0
        assert "Scrolled up x5" in result.output
        provider.scroll.assert_called_once_with("up", 5)

    def test_window_list(self, mock_submodules, runner):
        """window list command shows all windows."""
        provider = mock_submodules["peekxd.window"]
        provider.list_windows.return_value = [
            {"id": "0x01", "title": "Terminal", "class": "terminal"},
            {"id": "0x02", "title": "Browser", "class": "firefox"},
        ]
        result = runner.invoke(cli, ["window", "list"])
        assert result.exit_code == 0
        assert "Terminal" in result.output
        assert "Browser" in result.output

    def test_window_focus(self, mock_submodules, runner):
        """window focus command focuses a window."""
        provider = mock_submodules["peekxd.window"]
        result = runner.invoke(cli, ["window", "focus", "0x01"])
        assert result.exit_code == 0
        assert "Focused window 0x01" in result.output
        provider.focus_window.assert_called_once_with("0x01")

    def test_window_move(self, mock_submodules, runner):
        """window move command moves a window."""
        provider = mock_submodules["peekxd.window"]
        result = runner.invoke(cli, ["window", "move", "0x01", "10", "20"])
        assert result.exit_code == 0
        assert "Moved window 0x01 to 10,20" in result.output
        provider.move_window.assert_called_once_with("0x01", 10, 20)

    def test_window_resize(self, mock_submodules, runner):
        """window resize command resizes a window."""
        provider = mock_submodules["peekxd.window"]
        result = runner.invoke(cli, ["window", "resize", "0x01", "800", "600"])
        assert result.exit_code == 0
        assert "Resized window 0x01 to 800x600" in result.output
        provider.resize_window.assert_called_once_with("0x01", 800, 600)

    def test_see_without_subcommand_does_not_invoke_screenshot_provider(self, runner):
        """`peekxd see` defaults to help/usage and should not capture."""
        with patch("peekxd.screenshot.get_screenshot_provider") as mock_get_screenshot:
            result = runner.invoke(cli, ["see", "--help"])

        assert result.exit_code == 0
        assert "See and analyze the screen" in result.output
        mock_get_screenshot.assert_not_called()

    def test_capture_screen_removed(self, mock_submodules, runner):
        """capture screen is removed and does not call screenshot provider."""
        provider = mock_submodules["peekxd.screenshot"]
        result = runner.invoke(cli, ["capture", "screen", "-o", "/tmp/test.png"])
        assert result.exit_code != 0
        assert "Visible screenshot capture is removed" in result.output
        provider.capture_screen.assert_not_called()

    def test_capture_window_removed(self, mock_submodules, runner):
        """capture window is removed and does not call screenshot provider."""
        provider = mock_submodules["peekxd.screenshot"]
        result = runner.invoke(cli, ["capture", "window", "--id", "0x01"])
        assert result.exit_code != 0
        assert "Visible screenshot capture is removed" in result.output
        provider.capture_window.assert_not_called()

    def test_capture_region_removed(self, mock_submodules, runner):
        """capture region is removed and does not call screenshot provider."""
        provider = mock_submodules["peekxd.screenshot"]
        result = runner.invoke(cli, ["capture", "region", "10", "20", "100", "200"])
        assert result.exit_code != 0
        assert "Visible screenshot capture is removed" in result.output
        provider.capture_region.assert_not_called()

    def test_inspect_tree_command(self, mock_submodules, runner):
        """inspect tree command invokes the inspection provider."""
        from peekxd.inspection.base import UIElement
        mock_provider = MagicMock()
        mock_provider.get_ui_tree.return_value = [
            UIElement(
                id="0:1",
                name="Search",
                role="button",
                position=(10, 20),
                size=(30, 40),
                parent=None,
                children=[],
                attributes={},
            )
        ]
        
        with patch("peekxd.inspection.get_inspection_provider", return_value=mock_provider):
            result = runner.invoke(cli, ["inspect", "tree", "--app", "test-app"])
        assert result.exit_code == 0
        assert "button" in result.output or "Search" in result.output
        mock_provider.get_ui_tree.assert_called_once_with("test-app")

    def test_inspect_find_command(self, mock_submodules, runner):
        """inspect find command invokes the inspection provider."""
        from peekxd.inspection.base import UIElement
        mock_provider = MagicMock()
        mock_provider.find_element.return_value = UIElement(
            id="0:1",
            name="Submit",
            role="button",
            position=(100, 200),
            size=(50, 30),
            parent=None,
            children=[],
            attributes={},
        )
        
        with patch("peekxd.inspection.get_inspection_provider", return_value=mock_provider):
            result = runner.invoke(cli, ["inspect", "find", "--name", "Submit", "--role", "button"])
        assert result.exit_code == 0
        assert "Submit" in result.output or "button" in result.output or "Found" in result.output
        mock_provider.find_element.assert_called_once_with(name="Submit", role="button")

    def test_analyze_command(self, mock_submodules, runner):
        """analyze command invokes the vision provider."""
        mock_provider = MagicMock()
        mock_provider.analyze.return_value = "A button labeled OK"
        
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"fake image")
            tmp_path = f.name
        
        try:
            with patch("peekxd.vision.get_vision_provider", return_value=mock_provider):
                result = runner.invoke(cli, ["analyze", tmp_path, "What is this?"])
            assert result.exit_code == 0
            assert "button" in result.output or "OK" in result.output
        finally:
            import os
            os.unlink(tmp_path)

    def test_config_get_command(self, mock_submodules, runner):
        """config get command retrieves a config value."""
        result = runner.invoke(cli, ["config", "get", "screenshot.format"])
        assert result.exit_code == 0
        assert "jpg" in result.output or "png" in result.output or "format" in result.output

    def test_permissions(self, mock_submodules, runner):
        """permissions command lists checks."""
        result = runner.invoke(cli, ["permissions"])
        assert result.exit_code == 0
        assert "Desktop:" in result.output
        assert "Screenshot:" in result.output
        assert "Input:" in result.output
        assert "Inspection:" in result.output
        assert "Window:" in result.output
        assert "Vision:" in result.output

    def test_permissions_reports_removed_screenshot_without_provider_probe(self, mock_submodules, runner):
        """permissions reports screenshot removal without probing screenshot providers."""
        mod = sys.modules["peekxd.screenshot"]

        result = runner.invoke(cli, ["permissions"])

        assert result.exit_code == 0
        assert "Screenshot: REMOVED (use semantic state)" in result.output
        assert "Input:" in result.output
        assert "Vision:" in result.output
        assert not hasattr(mod, "get_screenshot_provider") or callable(mod.get_screenshot_provider)

    def test_see_capture_removed(self, mock_submodules, runner):
        """legacy see capture path is removed in favor of see --semantic."""
        mod = sys.modules["peekxd.screenshot"]

        result = runner.invoke(cli, ["see", "capture"])

        assert result.exit_code != 0
        assert "Visible screenshot capture is removed" in result.output
        assert not hasattr(mod, "get_screenshot_provider") or callable(mod.get_screenshot_provider)

    def test_see_semantic_json_uses_inspection_without_screenshot(self, mock_submodules, runner):
        """see --semantic --json returns semantic envelope without screenshot provider."""
        from peekxd.inspection.base import UIElement

        inspection = mock_submodules["peekxd.inspection"]
        screenshot = mock_submodules["peekxd.screenshot"]
        inspection.get_ui_tree.return_value = [
            UIElement(
                id="0:1",
                name="Search",
                role="button",
                position=(10, 20),
                size=(30, 40),
                parent=None,
                children=[],
                attributes={"label": "Find", "enabled": True, "focused": False},
            )
        ]
        mock_submodules["peekxd.window"].list_windows.return_value = [
            {"id": "0x1", "title": "Browser", "class": "firefox", "x": 1, "y": 2, "width": 800, "height": 600}
        ]

        result = runner.invoke(cli, ["see", "--semantic", "--json", "--app", "firefox"])

        assert result.exit_code == 0, result.output
        envelope = json.loads(result.output)
        assert envelope["schema_version"] == "peekxd.see.v1"
        assert envelope["command"] == "see --semantic"
        assert envelope["result"] == {"ok": True, "error": None}
        assert envelope["request"]["app"] == "firefox"
        assert envelope["snapshot"]["snapshot_id"].startswith("snap_")
        assert envelope["snapshot"]["elements"][0]["element_id"] == "W1-B1"
        assert envelope["snapshot"]["elements"][0]["raw_element_id"] == "0:1"
        assert envelope["snapshot"]["elements"][0]["bbox"] == {"x": 10, "y": 20, "width": 30, "height": 40}
        assert envelope["snapshot"]["windows"][0]["window_id"] == "W1"
        assert envelope["safety_state"]["code"] == "SEMANTIC_OK"
        screenshot.get_screenshot_provider.assert_not_called()

    def test_see_semantic_hud_shows_stable_element_ids(self, mock_submodules, runner):
        """see --semantic default HUD renders operator-friendly element ids."""
        from peekxd.inspection.base import UIElement

        mock_submodules["peekxd.inspection"].get_ui_tree.return_value = [
            UIElement("raw-text", "Address", "text", (5, 6), (100, 20), None, [], {}),
            UIElement("raw-button", "Go", "button", (120, 6), (32, 20), None, [], {}),
        ]

        result = runner.invoke(cli, ["see", "--semantic", "--max-elements", "2"])

        assert result.exit_code == 0, result.output
        assert "snapshot=snap_" in result.output
        assert "schema=peekxd.see.v1" in result.output
        assert "elements=2 shown=2" in result.output
        assert "W1-T1 text" in result.output
        assert "W1-B2 button" in result.output
        mock_submodules["peekxd.screenshot"].get_screenshot_provider.assert_not_called()

