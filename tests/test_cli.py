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

    def test_capture_screen(self, mock_submodules, runner):
        """capture screen command takes a screenshot."""
        provider = mock_submodules["peekxd.screenshot"]
        provider.capture_screen.return_value = "/tmp/test.png"
        result = runner.invoke(cli, ["capture", "screen", "-o", "/tmp/test.png"])
        assert result.exit_code == 0
        assert "Saved" in result.output
        provider.capture_screen.assert_called_once()

    def test_capture_window(self, mock_submodules, runner):
        """capture window command takes a window screenshot."""
        provider = mock_submodules["peekxd.screenshot"]
        provider.capture_window.return_value = "/tmp/win.png"
        result = runner.invoke(cli, ["capture", "window", "--id", "0x01"])
        assert result.exit_code == 0
        assert "Saved" in result.output
        provider.capture_window.assert_called_once()

    def test_capture_region(self, mock_submodules, runner):
        """capture region command captures a region."""
        provider = mock_submodules["peekxd.screenshot"]
        provider.capture_region.return_value = "/tmp/region.png"
        result = runner.invoke(cli, ["capture", "region", "10", "20", "100", "200"])
        assert result.exit_code == 0
        assert "Saved" in result.output
        provider.capture_region.assert_called_once()

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
