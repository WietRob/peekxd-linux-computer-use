"""Tests for the input module."""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

# Ensure peekxd is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from peekxd.core.desktop import DesktopEnvironment, detect_desktop
from peekxd.core.errors import (
    ProviderNotAvailableError,
    InputError,
    peekxdError,
)
from peekxd.input import (
    InputProvider,
    X11InputProvider,
    WaylandInputProvider,
    get_input_provider,
)
from peekxd.input.base import InputProvider as InputProviderBase
from peekxd.input.x11 import _BUTTON_MAP as x11_buttons, _SCROLL_MAP as x11_scroll
from peekxd.input.wayland import (
    _BUTTON_MAP as wl_buttons,
    _SCROLL_MAP as wl_scroll,
    _YDOTOOLD_SOCKET_PATHS,
    _ydotoold_running,
)


# ---------------------------------------------------------------------------
# InputProvider ABC
# ---------------------------------------------------------------------------


class DummyProvider(InputProviderBase):
    """Minimal concrete implementation for ABC testing."""

    def move_mouse(self, x: int, y: int) -> None:
        pass

    def click(self, x: int, y: int, button: str = "left") -> None:
        pass

    def double_click(self, x: int, y: int) -> None:
        pass

    def right_click(self, x: int, y: int) -> None:
        pass

    def type_text(self, text: str) -> None:
        pass

    def key_press(self, key: str) -> None:
        pass

    def hotkey(self, *keys: str) -> None:
        pass

    def scroll(self, direction: str = "down", amount: int = 3) -> None:
        pass

    def drag(self, x1: int, y1: int, x2: int, y2: int) -> None:
        pass

    @property
    def available(self) -> bool:
        return True


def test_abc_cannot_instantiate_directly() -> None:
    """Verify the abstract base class cannot be instantiated."""
    with pytest.raises(TypeError):
        InputProviderBase()


def test_dummy_provider_is_available() -> None:
    """A concrete provider should be instantiable and report availability."""
    provider = DummyProvider()
    assert provider.available is True


# ---------------------------------------------------------------------------
# X11 Input Provider — availability
# ---------------------------------------------------------------------------


class TestX11Availability:
    """Tests for X11InputProvider.availability."""

    @patch("peekxd.input.x11.executable_available")
    def test_available_when_xdotool_installed(self, mock_exec: MagicMock) -> None:
        mock_exec.return_value = True
        provider = X11InputProvider()
        assert provider.available is True
        mock_exec.assert_called_once_with("xdotool")

    @patch("peekxd.input.x11.executable_available")
    def test_not_available_when_xdotool_missing(self, mock_exec: MagicMock) -> None:
        mock_exec.return_value = False
        provider = X11InputProvider()
        assert provider.available is False
        mock_exec.assert_called_once_with("xdotool")


# ---------------------------------------------------------------------------
# X11 Input Provider — command execution
# ---------------------------------------------------------------------------


class TestX11Commands:
    """Tests for X11InputProvider command generation."""

    @patch("peekxd.input.x11.run_command")
    @patch("peekxd.input.x11.executable_available")
    def test_move_mouse(self, mock_avail: MagicMock, mock_run: MagicMock) -> None:
        mock_avail.return_value = True
        provider = X11InputProvider()
        provider.move_mouse(100, 200)
        mock_run.assert_called_once_with(["xdotool", "mousemove", "100", "200"])

    @patch("peekxd.input.x11.run_command")
    @patch("peekxd.input.x11.executable_available")
    def test_click_default(self, mock_avail: MagicMock, mock_run: MagicMock) -> None:
        mock_avail.return_value = True
        provider = X11InputProvider()
        provider.click(50, 75)
        mock_run.assert_called_once_with(["xdotool", "mousemove", "50", "75", "click", "1"])

    @patch("peekxd.input.x11.run_command")
    @patch("peekxd.input.x11.executable_available")
    def test_click_right(self, mock_avail: MagicMock, mock_run: MagicMock) -> None:
        mock_avail.return_value = True
        provider = X11InputProvider()
        provider.click(10, 20, button="right")
        mock_run.assert_called_once_with(["xdotool", "mousemove", "10", "20", "click", "3"])

    @patch("peekxd.input.x11.run_command")
    @patch("peekxd.input.x11.executable_available")
    def test_double_click(self, mock_avail: MagicMock, mock_run: MagicMock) -> None:
        mock_avail.return_value = True
        provider = X11InputProvider()
        provider.double_click(100, 100)
        mock_run.assert_called_once_with(
            ["xdotool", "mousemove", "100", "100", "click", "--repeat", "2", "1"]
        )

    @patch("peekxd.input.x11.run_command")
    @patch("peekxd.input.x11.executable_available")
    def test_right_click(self, mock_avail: MagicMock, mock_run: MagicMock) -> None:
        mock_avail.return_value = True
        provider = X11InputProvider()
        provider.right_click(30, 40)
        mock_run.assert_called_once_with(["xdotool", "mousemove", "30", "40", "click", "3"])

    @patch("peekxd.input.x11.run_command")
    @patch("peekxd.input.x11.executable_available")
    def test_type_text(self, mock_avail: MagicMock, mock_run: MagicMock) -> None:
        mock_avail.return_value = True
        provider = X11InputProvider()
        provider.type_text("hello")
        mock_run.assert_called_once_with(["xdotool", "type", "--delay", "10", "hello"])

    @patch("peekxd.input.x11.run_command")
    @patch("peekxd.input.x11.executable_available")
    def test_type_text_with_quotes(self, mock_avail: MagicMock, mock_run: MagicMock) -> None:
        mock_avail.return_value = True
        provider = X11InputProvider()
        provider.type_text("it's a test")
        mock_run.assert_called_once_with(
            ["xdotool", "type", "--delay", "10", "it'\"'\"'s a test"]
        )

    @patch("peekxd.input.x11.run_command")
    @patch("peekxd.input.x11.executable_available")
    def test_key_press(self, mock_avail: MagicMock, mock_run: MagicMock) -> None:
        mock_avail.return_value = True
        provider = X11InputProvider()
        provider.key_press("Return")
        mock_run.assert_called_once_with(["xdotool", "key", "Return"])

    @patch("peekxd.input.x11.run_command")
    @patch("peekxd.input.x11.executable_available")
    def test_hotkey(self, mock_avail: MagicMock, mock_run: MagicMock) -> None:
        mock_avail.return_value = True
        provider = X11InputProvider()
        provider.hotkey("ctrl", "alt", "t")
        mock_run.assert_called_once_with(["xdotool", "key", "ctrl+alt+t"])

    @patch("peekxd.input.x11.run_command")
    @patch("peekxd.input.x11.executable_available")
    def test_scroll_down(self, mock_avail: MagicMock, mock_run: MagicMock) -> None:
        mock_avail.return_value = True
        provider = X11InputProvider()
        provider.scroll(direction="down", amount=3)
        assert mock_run.call_count == 3
        for c in mock_run.call_args_list:
            assert c == call(["xdotool", "click", "5"])

    @patch("peekxd.input.x11.run_command")
    @patch("peekxd.input.x11.executable_available")
    def test_scroll_up(self, mock_avail: MagicMock, mock_run: MagicMock) -> None:
        mock_avail.return_value = True
        provider = X11InputProvider()
        provider.scroll(direction="up", amount=2)
        assert mock_run.call_count == 2
        for c in mock_run.call_args_list:
            assert c == call(["xdotool", "click", "4"])

    @patch("peekxd.input.x11.run_command")
    @patch("peekxd.input.x11.executable_available")
    def test_drag(self, mock_avail: MagicMock, mock_run: MagicMock) -> None:
        mock_avail.return_value = True
        provider = X11InputProvider()
        provider.drag(10, 20, 100, 200)
        mock_run.assert_called_once_with(
            [
                "xdotool",
                "mousemove", "10", "20",
                "mousedown", "1",
                "mousemove", "100", "200",
                "mouseup", "1",
            ]
        )

    @patch("peekxd.input.x11.run_command", side_effect=peekxdError("xdotool failed"))
    @patch("peekxd.input.x11.executable_available")
    def test_command_failure_raises_input_error(self, mock_avail: MagicMock, mock_run: MagicMock) -> None:
        mock_avail.return_value = True
        provider = X11InputProvider()
        with pytest.raises(InputError):
            provider.move_mouse(0, 0)


# ---------------------------------------------------------------------------
# Wayland Input Provider — availability
# ---------------------------------------------------------------------------


class TestWaylandAvailability:
    """Tests for WaylandInputProvider.availability."""

    @patch("peekxd.input.wayland.executable_available")
    @patch("peekxd.input.wayland._ydotoold_running")
    def test_available_when_ydotool_and_daemon_present(
        self, mock_daemon: MagicMock, mock_exec: MagicMock
    ) -> None:
        mock_exec.return_value = True
        mock_daemon.return_value = True
        provider = WaylandInputProvider()
        assert provider.available is True
        mock_exec.assert_called_once_with("ydotool")
        mock_daemon.assert_called_once()

    @patch("peekxd.input.wayland.executable_available")
    @patch("peekxd.input.wayland._ydotoold_running")
    def test_not_available_when_ydotool_missing(
        self, mock_daemon: MagicMock, mock_exec: MagicMock
    ) -> None:
        mock_exec.return_value = False
        mock_daemon.return_value = True
        provider = WaylandInputProvider()
        assert provider.available is False

    @patch("peekxd.input.wayland.executable_available")
    @patch("peekxd.input.wayland._ydotoold_running")
    def test_not_available_when_daemon_missing(
        self, mock_daemon: MagicMock, mock_exec: MagicMock
    ) -> None:
        mock_exec.return_value = True
        mock_daemon.return_value = False
        provider = WaylandInputProvider()
        assert provider.available is False

    @patch("peekxd.input.wayland.Path.exists")
    def test_ydotoold_running_checks_socket_paths(self, mock_exists: MagicMock) -> None:
        """The daemon check should iterate through known socket paths."""
        mock_exists.side_effect = [False, False, True]  # third path exists
        result = _ydotoold_running()
        assert result is True
        assert mock_exists.call_count == 3

    @patch("peekxd.input.wayland.Path.exists", return_value=False)
    def test_ydotoold_running_returns_false_when_no_socket(self, mock_exists: MagicMock) -> None:
        result = _ydotoold_running()
        assert result is False


# ---------------------------------------------------------------------------
# Wayland Input Provider — command execution
# ---------------------------------------------------------------------------


class TestWaylandCommands:
    """Tests for WaylandInputProvider command generation."""

    @patch("peekxd.input.wayland._ydotoold_running")
    @patch("peekxd.input.wayland.run_command")
    @patch("peekxd.input.wayland.executable_available")
    def test_move_mouse(self, mock_avail: MagicMock, mock_run: MagicMock, mock_daemon: MagicMock) -> None:
        mock_avail.return_value = True
        mock_daemon.return_value = True
        provider = WaylandInputProvider()
        provider.move_mouse(100, 200)
        mock_run.assert_called_once_with(["ydotool", "mousemove", "100", "200"])

    @patch("peekxd.input.wayland._ydotoold_running")
    @patch("peekxd.input.wayland.run_command")
    @patch("peekxd.input.wayland.executable_available")
    def test_click(self, mock_avail: MagicMock, mock_run: MagicMock, mock_daemon: MagicMock) -> None:
        mock_avail.return_value = True
        mock_daemon.return_value = True
        provider = WaylandInputProvider()
        provider.click(50, 75)
        # Should call mousemove then click
        assert mock_run.call_count == 2
        mock_run.assert_any_call(["ydotool", "mousemove", "50", "75"])
        mock_run.assert_any_call(["ydotool", "click", "0xC0"])

    @patch("peekxd.input.wayland._ydotoold_running")
    @patch("peekxd.input.wayland.run_command")
    @patch("peekxd.input.wayland.executable_available")
    def test_double_click(self, mock_avail: MagicMock, mock_run: MagicMock, mock_daemon: MagicMock) -> None:
        mock_avail.return_value = True
        mock_daemon.return_value = True
        provider = WaylandInputProvider()
        provider.double_click(100, 100)
        assert mock_run.call_count == 2
        mock_run.assert_any_call(["ydotool", "mousemove", "100", "100"])
        mock_run.assert_any_call(["ydotool", "click", "0xC0", "2"])

    @patch("peekxd.input.wayland._ydotoold_running")
    @patch("peekxd.input.wayland.run_command")
    @patch("peekxd.input.wayland.executable_available")
    def test_right_click(self, mock_avail: MagicMock, mock_run: MagicMock, mock_daemon: MagicMock) -> None:
        mock_avail.return_value = True
        mock_daemon.return_value = True
        provider = WaylandInputProvider()
        provider.right_click(30, 40)
        assert mock_run.call_count == 2
        mock_run.assert_any_call(["ydotool", "mousemove", "30", "40"])
        mock_run.assert_any_call(["ydotool", "click", "0xC1"])

    @patch("peekxd.input.wayland._ydotoold_running")
    @patch("peekxd.input.wayland.run_command")
    @patch("peekxd.input.wayland.executable_available")
    def test_type_text(self, mock_avail: MagicMock, mock_run: MagicMock, mock_daemon: MagicMock) -> None:
        mock_avail.return_value = True
        mock_daemon.return_value = True
        provider = WaylandInputProvider()
        provider.type_text("hello")
        mock_run.assert_called_once_with(["ydotool", "type", "hello"])

    @patch("peekxd.input.wayland._ydotoold_running")
    @patch("peekxd.input.wayland.run_command")
    @patch("peekxd.input.wayland.executable_available")
    def test_type_text_with_quotes(self, mock_avail: MagicMock, mock_run: MagicMock, mock_daemon: MagicMock) -> None:
        mock_avail.return_value = True
        mock_daemon.return_value = True
        provider = WaylandInputProvider()
        provider.type_text("it's a test")
        mock_run.assert_called_once_with(["ydotool", "type", "it'\"'\"'s a test"])

    @patch("peekxd.input.wayland._ydotoold_running")
    @patch("peekxd.input.wayland.run_command")
    @patch("peekxd.input.wayland.executable_available")
    def test_key_press(self, mock_avail: MagicMock, mock_run: MagicMock, mock_daemon: MagicMock) -> None:
        mock_avail.return_value = True
        mock_daemon.return_value = True
        provider = WaylandInputProvider()
        provider.key_press("Return")
        mock_run.assert_called_once_with(["ydotool", "key", "Return"])

    @patch("peekxd.input.wayland._ydotoold_running")
    @patch("peekxd.input.wayland.run_command")
    @patch("peekxd.input.wayland.executable_available")
    def test_hotkey(self, mock_avail: MagicMock, mock_run: MagicMock, mock_daemon: MagicMock) -> None:
        mock_avail.return_value = True
        mock_daemon.return_value = True
        provider = WaylandInputProvider()
        provider.hotkey("ctrl", "alt", "t")
        # ydotool uses comma separator
        mock_run.assert_called_once_with(["ydotool", "key", "ctrl,alt,t"])

    @patch("peekxd.input.wayland._ydotoold_running")
    @patch("peekxd.input.wayland.run_command")
    @patch("peekxd.input.wayland.executable_available")
    def test_scroll_down(self, mock_avail: MagicMock, mock_run: MagicMock, mock_daemon: MagicMock) -> None:
        mock_avail.return_value = True
        mock_daemon.return_value = True
        provider = WaylandInputProvider()
        provider.scroll(direction="down", amount=3)
        assert mock_run.call_count == 3
        for c in mock_run.call_args_list:
            assert c == call(["ydotool", "click", "5"])

    @patch("peekxd.input.wayland._ydotoold_running")
    @patch("peekxd.input.wayland.run_command")
    @patch("peekxd.input.wayland.executable_available")
    def test_drag(self, mock_avail: MagicMock, mock_run: MagicMock, mock_daemon: MagicMock) -> None:
        mock_avail.return_value = True
        mock_daemon.return_value = True
        provider = WaylandInputProvider()
        provider.drag(10, 20, 100, 200)
        assert mock_run.call_count == 4
        mock_run.assert_any_call(["ydotool", "mousemove", "10", "20"])
        mock_run.assert_any_call(["ydotool", "mousedown", "0xC0"])
        mock_run.assert_any_call(["ydotool", "mousemove", "100", "200"])
        mock_run.assert_any_call(["ydotool", "mouseup", "0xC0"])

    @patch("peekxd.input.wayland._ydotoold_running")
    @patch("peekxd.input.wayland.run_command", side_effect=peekxdError("ydotool failed"))
    @patch("peekxd.input.wayland.executable_available")
    def test_command_failure_raises_input_error(
        self, mock_avail: MagicMock, mock_run: MagicMock, mock_daemon: MagicMock
    ) -> None:
        mock_avail.return_value = True
        mock_daemon.return_value = True
        provider = WaylandInputProvider()
        with pytest.raises(InputError):
            provider.move_mouse(0, 0)


# ---------------------------------------------------------------------------
# Detector / get_input_provider
# ---------------------------------------------------------------------------


class TestGetInputProvider:
    """Tests for the auto-detection logic."""

    @patch("peekxd.input.detector.detect_desktop")
    @patch("peekxd.input.x11.executable_available")
    def test_returns_x11_on_x11_desktop(
        self, mock_exec: MagicMock, mock_detect: MagicMock
    ) -> None:
        mock_detect.return_value = DesktopEnvironment.X11
        mock_exec.return_value = True
        provider = get_input_provider()
        assert isinstance(provider, X11InputProvider)

    @patch("peekxd.input.detector.detect_desktop")
    @patch("peekxd.input.wayland.executable_available")
    @patch("peekxd.input.wayland._ydotoold_running")
    def test_returns_wayland_on_wayland_desktop(
        self, mock_daemon: MagicMock, mock_exec: MagicMock, mock_detect: MagicMock
    ) -> None:
        mock_detect.return_value = DesktopEnvironment.WAYLAND
        mock_exec.return_value = True
        mock_daemon.return_value = True
        provider = get_input_provider()
        assert isinstance(provider, WaylandInputProvider)

    @patch("peekxd.input.detector.detect_desktop")
    @patch("peekxd.input.wayland.executable_available")
    @patch("peekxd.input.wayland._ydotoold_running")
    @patch("peekxd.input.x11.executable_available")
    def test_x11_fallback_when_wayland_unavailable(
        self, mock_x11_exec: MagicMock, mock_daemon: MagicMock, mock_wl_exec: MagicMock, mock_detect: MagicMock
    ) -> None:
        """On Wayland desktop, if Wayland provider unavailable, fallback to X11."""
        mock_detect.return_value = DesktopEnvironment.WAYLAND
        mock_wl_exec.return_value = False  # ydotool not installed
        mock_x11_exec.return_value = True  # xdotool available
        provider = get_input_provider()
        assert isinstance(provider, X11InputProvider)

    @patch("peekxd.input.detector.detect_desktop")
    @patch("peekxd.input.wayland.executable_available")
    @patch("peekxd.input.wayland._ydotoold_running")
    @patch("peekxd.input.x11.executable_available")
    def test_wayland_fallback_when_x11_unavailable(
        self, mock_x11_exec: MagicMock, mock_daemon: MagicMock, mock_wl_exec: MagicMock, mock_detect: MagicMock
    ) -> None:
        """On X11 desktop, if X11 provider unavailable, fallback to Wayland."""
        mock_detect.return_value = DesktopEnvironment.X11
        mock_x11_exec.return_value = False  # xdotool not installed
        mock_wl_exec.return_value = True   # ydotool installed
        mock_daemon.return_value = True    # ydotoold running
        provider = get_input_provider()
        assert isinstance(provider, WaylandInputProvider)

    @patch("peekxd.input.detector.detect_desktop")
    @patch("peekxd.input.x11.executable_available")
    @patch("peekxd.input.wayland.executable_available")
    def test_raises_when_no_provider_available(
        self, mock_wl_exec: MagicMock, mock_x11_exec: MagicMock, mock_detect: MagicMock
    ) -> None:
        mock_detect.return_value = DesktopEnvironment.UNKNOWN
        mock_x11_exec.return_value = False
        mock_wl_exec.return_value = False
        with pytest.raises(ProviderNotAvailableError) as exc_info:
            get_input_provider()
        assert "xdotool" in str(exc_info.value)
        assert "ydotool" in str(exc_info.value)

    @patch("peekxd.input.detector.detect_desktop")
    @patch("peekxd.input.x11.executable_available")
    def test_unknown_desktop_prefers_x11(
        self, mock_exec: MagicMock, mock_detect: MagicMock
    ) -> None:
        mock_detect.return_value = DesktopEnvironment.UNKNOWN
        mock_exec.return_value = True  # xdotool available
        provider = get_input_provider()
        assert isinstance(provider, X11InputProvider)


# ---------------------------------------------------------------------------
# Button / scroll mapping constants
# ---------------------------------------------------------------------------


def test_x11_button_map() -> None:
    assert x11_buttons["left"] == 1
    assert x11_buttons["middle"] == 2
    assert x11_buttons["right"] == 3


def test_x11_scroll_map() -> None:
    assert x11_scroll["up"] == 4
    assert x11_scroll["down"] == 5
    assert x11_scroll["left"] == 6
    assert x11_scroll["right"] == 7


def test_wayland_button_map() -> None:
    assert wl_buttons["left"] == "0xC0"
    assert wl_buttons["right"] == "0xC1"
    assert wl_buttons["middle"] == "0xC2"


def test_wayland_scroll_map() -> None:
    assert wl_scroll["up"] == "4"
    assert wl_scroll["down"] == "5"
    assert wl_scroll["left"] == "6"
    assert wl_scroll["right"] == "7"


# ---------------------------------------------------------------------------
# Module exports
# ---------------------------------------------------------------------------


def test_module_exports() -> None:
    """Verify __init__.py exports all expected names."""
    from peekxd import input as input_module

    assert hasattr(input_module, "InputProvider")
    assert hasattr(input_module, "X11InputProvider")
    assert hasattr(input_module, "WaylandInputProvider")
    assert hasattr(input_module, "get_input_provider")
