"""Tests for the peekxd window management module."""

import json
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from peekxd.core.desktop import DesktopEnvironment
from peekxd.core.errors import ProviderNotAvailableError, WindowError
from peekxd.window.base import WindowProvider
from peekxd.window.x11 import X11WindowProvider
from peekxd.window.wayland import WaylandWindowProvider
from peekxd.window.detector import get_window_provider


# ============================================================================
# Helpers
# ============================================================================


def _completed_process(stdout: str = "", stderr: str = "", returncode: int = 0):
    """Build a mock subprocess.CompletedProcess."""
    result = MagicMock(spec=subprocess.CompletedProcess)
    result.stdout = stdout
    result.stderr = stderr
    result.returncode = returncode
    return result


# ============================================================================
# X11WindowProvider tests
# ============================================================================


class TestX11WindowProvider:
    """Tests for X11WindowProvider."""

    # -- availability -------------------------------------------------------

    @patch("peekxd.window.x11.executable_available")
    def test_available_when_xdotool_installed(self, mock_avail):
        mock_avail.return_value = True
        provider = X11WindowProvider()
        assert provider.available is True

    @patch("peekxd.window.x11.executable_available")
    def test_not_available_when_xdotool_missing(self, mock_avail):
        mock_avail.return_value = False
        provider = X11WindowProvider()
        assert provider.available is False

    # -- list_windows -------------------------------------------------------

    @patch("peekxd.window.x11.executable_available")
    @patch.object(X11WindowProvider, "_run_xdotool")
    @patch.object(X11WindowProvider, "_get_window_name")
    @patch.object(X11WindowProvider, "_get_window_geometry")
    def test_list_windows_success(self, mock_geo, mock_name, mock_run, mock_avail):
        mock_avail.return_value = True
        mock_run.return_value = _completed_process(
            stdout="12345\n67890\n", returncode=0
        )
        mock_name.side_effect = ["Terminal", "Browser"]
        mock_geo.side_effect = [
            {"x": 10, "y": 20, "width": 800, "height": 600},
            {"x": 100, "y": 200, "width": 1024, "height": 768},
        ]

        provider = X11WindowProvider()
        windows = provider.list_windows()

        assert len(windows) == 2
        assert windows[0]["id"] == "12345"
        assert windows[0]["name"] == "Terminal"
        assert windows[0]["x"] == 10
        assert windows[0]["width"] == 800
        assert windows[1]["id"] == "67890"
        assert windows[1]["name"] == "Browser"

    @patch("peekxd.window.x11.executable_available")
    @patch.object(X11WindowProvider, "_run_xdotool")
    def test_list_windows_empty(self, mock_run, mock_avail):
        mock_avail.return_value = True
        mock_run.return_value = _completed_process(stdout="", returncode=0)
        provider = X11WindowProvider()
        assert provider.list_windows() == []

    @patch("peekxd.window.x11.executable_available")
    @patch.object(X11WindowProvider, "_run_xdotool")
    def test_list_windows_xdotool_error(self, mock_run, mock_avail):
        mock_avail.return_value = True
        mock_run.return_value = _completed_process(
            stdout="", stderr="error", returncode=1
        )
        provider = X11WindowProvider()
        assert provider.list_windows() == []

    # -- focus_window -------------------------------------------------------

    @patch("peekxd.window.x11.executable_available")
    @patch.object(X11WindowProvider, "_run_xdotool")
    def test_focus_window_success(self, mock_run, mock_avail):
        mock_avail.return_value = True
        mock_run.return_value = _completed_process(returncode=0)
        provider = X11WindowProvider()
        provider.focus_window("12345")
        mock_run.assert_called_once_with(["windowactivate", "12345"])

    @patch("peekxd.window.x11.executable_available")
    @patch.object(X11WindowProvider, "_run_xdotool")
    def test_focus_window_error(self, mock_run, mock_avail):
        mock_avail.return_value = True
        mock_run.side_effect = WindowError("xdotool failed")
        provider = X11WindowProvider()
        with pytest.raises(WindowError):
            provider.focus_window("12345")

    # -- move_window --------------------------------------------------------

    @patch("peekxd.window.x11.executable_available")
    @patch.object(X11WindowProvider, "_run_xdotool")
    def test_move_window_success(self, mock_run, mock_avail):
        mock_avail.return_value = True
        mock_run.return_value = _completed_process(returncode=0)
        provider = X11WindowProvider()
        provider.move_window("12345", 100, 200)
        mock_run.assert_called_once_with(["windowmove", "12345", "100", "200"])

    # -- resize_window ------------------------------------------------------

    @patch("peekxd.window.x11.executable_available")
    @patch.object(X11WindowProvider, "_run_xdotool")
    def test_resize_window_success(self, mock_run, mock_avail):
        mock_avail.return_value = True
        mock_run.return_value = _completed_process(returncode=0)
        provider = X11WindowProvider()
        provider.resize_window("12345", 800, 600)
        mock_run.assert_called_once_with(["windowsize", "12345", "800", "600"])

    # -- close_window -------------------------------------------------------

    @patch("peekxd.window.x11.executable_available")
    @patch.object(X11WindowProvider, "_run_xdotool")
    def test_close_window_graceful(self, mock_run, mock_avail):
        mock_avail.return_value = True
        mock_run.return_value = _completed_process(returncode=0)
        provider = X11WindowProvider()
        provider.close_window("12345")
        mock_run.assert_called_once_with(["windowclose", "12345"])

    @patch("peekxd.window.x11.executable_available")
    @patch.object(X11WindowProvider, "_run_xdotool")
    def test_close_window_fallback_kill(self, mock_run, mock_avail):
        mock_avail.return_value = True
        mock_run.side_effect = [
            WindowError("close failed"),
            _completed_process(returncode=0),
        ]
        provider = X11WindowProvider()
        provider.close_window("12345")
        assert mock_run.call_count == 2
        mock_run.assert_called_with(["windowkill", "12345"])

    # -- get_active_window --------------------------------------------------

    @patch("peekxd.window.x11.executable_available")
    @patch.object(X11WindowProvider, "_run_xdotool")
    @patch.object(X11WindowProvider, "_get_window_name")
    @patch.object(X11WindowProvider, "_get_window_geometry")
    def test_get_active_window_success(self, mock_geo, mock_name, mock_run, mock_avail):
        mock_avail.return_value = True
        mock_run.return_value = _completed_process(stdout="12345", returncode=0)
        mock_name.return_value = "Active Window"
        mock_geo.return_value = {"x": 0, "y": 0, "width": 1920, "height": 1080}

        provider = X11WindowProvider()
        window = provider.get_active_window()

        assert window is not None
        assert window["id"] == "12345"
        assert window["name"] == "Active Window"

    @patch("peekxd.window.x11.executable_available")
    @patch.object(X11WindowProvider, "_run_xdotool")
    def test_get_active_window_none(self, mock_run, mock_avail):
        mock_avail.return_value = True
        mock_run.side_effect = WindowError("no active window")
        provider = X11WindowProvider()
        assert provider.get_active_window() is None

    # -- launch_app ---------------------------------------------------------

    @patch("peekxd.window.x11.executable_available")
    @patch.object(X11WindowProvider, "_run_xdotool")
    def test_launch_app_xdotool(self, mock_run, mock_avail):
        mock_avail.return_value = True
        mock_run.return_value = _completed_process(returncode=0)
        provider = X11WindowProvider()
        provider.launch_app("firefox")
        mock_run.assert_called_once_with(["exec", "firefox"])

    @patch("peekxd.window.x11.executable_available")
    @patch.object(X11WindowProvider, "_run_xdotool")
    @patch("subprocess.Popen")
    def test_launch_app_fallback(self, mock_popen, mock_run, mock_avail):
        mock_avail.return_value = True
        mock_run.side_effect = WindowError("xdotool exec failed")
        mock_popen.return_value = MagicMock()
        provider = X11WindowProvider()
        provider.launch_app("firefox")
        mock_popen.assert_called_once()

    # -- geometry parsing ---------------------------------------------------

    @patch("peekxd.window.x11.executable_available")
    @patch.object(X11WindowProvider, "_run_xdotool")
    def test_get_window_geometry_parsing(self, mock_run, mock_avail):
        mock_avail.return_value = True
        mock_run.return_value = _completed_process(
            stdout="Window 12345\n  Position: 150,250 (screen: 0)\n  Geometry: 1024x768\n",
            returncode=0,
        )
        provider = X11WindowProvider()
        geo = provider._get_window_geometry("12345")
        assert geo == {"x": 150, "y": 250, "width": 1024, "height": 768}

    @patch("peekxd.window.x11.executable_available")
    @patch.object(X11WindowProvider, "_run_xdotool")
    def test_get_window_geometry_error_fallback(self, mock_run, mock_avail):
        mock_avail.return_value = True
        mock_run.return_value = _completed_process(
            stdout="", stderr="error", returncode=1
        )
        provider = X11WindowProvider()
        geo = provider._get_window_geometry("12345")
        assert geo == {"x": 0, "y": 0, "width": 0, "height": 0}


# ============================================================================
# WaylandWindowProvider tests
# ============================================================================


class TestWaylandWindowProvider:
    """Tests for WaylandWindowProvider."""

    # -- availability -------------------------------------------------------

    @patch("peekxd.window.wayland.executable_available")
    def test_available_wlrctl(self, mock_avail):
        mock_avail.side_effect = lambda name: name == "wlrctl"
        provider = WaylandWindowProvider()
        assert provider.available is True

    @patch("peekxd.window.wayland.executable_available")
    def test_available_swaymsg(self, mock_avail):
        mock_avail.side_effect = lambda name: name == "swaymsg"
        provider = WaylandWindowProvider()
        assert provider.available is True

    @patch("peekxd.window.wayland.executable_available")
    def test_not_available(self, mock_avail):
        mock_avail.return_value = False
        provider = WaylandWindowProvider()
        assert provider.available is False

    # -- list_windows via swaymsg -------------------------------------------

    @patch("peekxd.window.wayland.executable_available")
    @patch.object(WaylandWindowProvider, "_run_swaymsg")
    def test_list_windows_swaymsg(self, mock_sway, mock_avail):
        mock_avail.side_effect = lambda name: name == "swaymsg"
        tree = {
            "id": 1,
            "name": "root",
            "type": "root",
            "nodes": [
                {
                    "id": 2,
                    "name": "__i3",
                    "type": "output",
                    "nodes": [
                        {
                            "id": 3,
                            "name": "Workspace 1",
                            "type": "workspace",
                            "nodes": [
                                {
                                    "id": 42,
                                    "name": "Terminal",
                                    "type": "con",
                                    "app_id": "org.gnome.Terminal",
                                    "focused": False,
                                    "rect": {"x": 0, "y": 0, "width": 800, "height": 600},
                                    "window_rect": {"x": 2, "y": 24, "width": 796, "height": 574},
                                    "nodes": [],
                                    "floating_nodes": [],
                                }
                            ],
                            "floating_nodes": [],
                        }
                    ],
                    "floating_nodes": [],
                }
            ],
            "floating_nodes": [],
        }
        mock_sway.return_value = _completed_process(stdout=json.dumps(tree), returncode=0)

        provider = WaylandWindowProvider()
        windows = provider.list_windows()

        assert len(windows) == 1
        assert windows[0]["id"] == "42"
        assert windows[0]["name"] == "Terminal"
        assert windows[0]["app_id"] == "org.gnome.Terminal"

    @patch("peekxd.window.wayland.executable_available")
    @patch.object(WaylandWindowProvider, "_run_swaymsg")
    def test_list_windows_swaymsg_empty(self, mock_sway, mock_avail):
        mock_avail.side_effect = lambda name: name == "swaymsg"
        tree = {"id": 1, "name": "root", "type": "root", "nodes": [], "floating_nodes": []}
        mock_sway.return_value = _completed_process(stdout=json.dumps(tree), returncode=0)
        provider = WaylandWindowProvider()
        assert provider.list_windows() == []

    # -- sway tree parsing --------------------------------------------------

    @patch("peekxd.window.wayland.executable_available")
    def test_parse_sway_tree_focused(self, mock_avail):
        mock_avail.return_value = False
        tree = {
            "id": 42,
            "name": "Focused Window",
            "type": "con",
            "app_id": "app",
            "focused": True,
            "rect": {"x": 100, "y": 200, "width": 800, "height": 600},
            "window_rect": {"x": 0, "y": 0, "width": 796, "height": 574},
            "nodes": [],
            "floating_nodes": [],
        }
        provider = WaylandWindowProvider()
        active = provider._parse_sway_active(tree)
        assert active is not None
        assert active["id"] == "42"
        assert active["name"] == "Focused Window"
        assert active["x"] == 100

    # -- focus_window -------------------------------------------------------

    @patch("peekxd.window.wayland.executable_available")
    @patch.object(WaylandWindowProvider, "_run_swaymsg")
    def test_focus_window_swaymsg(self, mock_sway, mock_avail):
        mock_avail.side_effect = lambda name: name == "swaymsg"
        mock_sway.return_value = _completed_process(returncode=0)
        provider = WaylandWindowProvider()
        provider.focus_window("42")
        mock_sway.assert_called_once_with(["[con_id=42]", "focus"])

    @patch("peekxd.window.wayland.executable_available")
    @patch.object(WaylandWindowProvider, "_run_wlrctl")
    def test_focus_window_wlrctl(self, mock_wlrctl, mock_avail):
        mock_avail.side_effect = lambda name: name == "wlrctl"
        mock_wlrctl.return_value = _completed_process(returncode=0)
        provider = WaylandWindowProvider()
        provider.focus_window("My Window")
        mock_wlrctl.assert_called_once_with(["window", "focus", "My Window"])

    # -- move_window --------------------------------------------------------

    @patch("peekxd.window.wayland.executable_available")
    @patch.object(WaylandWindowProvider, "_run_swaymsg")
    def test_move_window_swaymsg(self, mock_sway, mock_avail):
        mock_avail.side_effect = lambda name: name == "swaymsg"
        mock_sway.return_value = _completed_process(returncode=0)
        provider = WaylandWindowProvider()
        provider.move_window("42", 100, 200)
        mock_sway.assert_called_once_with(["[con_id=42]", "move", "position", "100", "200"])

    # -- resize_window ------------------------------------------------------

    @patch("peekxd.window.wayland.executable_available")
    @patch.object(WaylandWindowProvider, "_run_swaymsg")
    def test_resize_window_swaymsg(self, mock_sway, mock_avail):
        mock_avail.side_effect = lambda name: name == "swaymsg"
        mock_sway.return_value = _completed_process(returncode=0)
        provider = WaylandWindowProvider()
        provider.resize_window("42", 800, 600)
        mock_sway.assert_called_once_with(["[con_id=42]", "resize", "set", "800", "600"])

    # -- close_window -------------------------------------------------------

    @patch("peekxd.window.wayland.executable_available")
    @patch.object(WaylandWindowProvider, "_run_swaymsg")
    def test_close_window_swaymsg(self, mock_sway, mock_avail):
        mock_avail.side_effect = lambda name: name == "swaymsg"
        mock_sway.return_value = _completed_process(returncode=0)
        provider = WaylandWindowProvider()
        provider.close_window("42")
        mock_sway.assert_called_once_with(["[con_id=42]", "kill"])

    # -- get_active_window --------------------------------------------------

    @patch("peekxd.window.wayland.executable_available")
    @patch.object(WaylandWindowProvider, "_run_swaymsg")
    def test_get_active_window_swaymsg(self, mock_sway, mock_avail):
        mock_avail.side_effect = lambda name: name == "swaymsg"
        tree = {
            "id": 42,
            "name": "Active",
            "type": "con",
            "app_id": "test",
            "focused": True,
            "rect": {"x": 0, "y": 0, "width": 500, "height": 400},
            "window_rect": {"x": 0, "y": 0, "width": 496, "height": 376},
            "nodes": [],
            "floating_nodes": [],
        }
        mock_sway.return_value = _completed_process(stdout=json.dumps(tree), returncode=0)
        provider = WaylandWindowProvider()
        active = provider.get_active_window()
        assert active is not None
        assert active["id"] == "42"
        assert active["name"] == "Active"

    # -- launch_app ---------------------------------------------------------

    @patch("peekxd.window.wayland.executable_available")
    @patch.object(WaylandWindowProvider, "_run_wlrctl")
    def test_launch_app_wlrctl(self, mock_wlrctl, mock_avail):
        mock_avail.side_effect = lambda name: name == "wlrctl"
        mock_wlrctl.return_value = _completed_process(returncode=0)
        provider = WaylandWindowProvider()
        provider.launch_app("firefox")
        mock_wlrctl.assert_called_once_with(["application", "launch", "firefox"])

    @patch("peekxd.window.wayland.executable_available")
    @patch.object(WaylandWindowProvider, "_run_wlrctl")
    @patch("subprocess.Popen")
    def test_launch_app_fallback(self, mock_popen, mock_wlrctl, mock_avail):
        mock_avail.side_effect = lambda name: name == "wlrctl"
        mock_wlrctl.side_effect = WindowError("wlrctl failed")
        mock_popen.return_value = MagicMock()
        provider = WaylandWindowProvider()
        provider.launch_app("firefox")
        mock_popen.assert_called_once()

    # -- error when no backend ----------------------------------------------

    @patch("peekxd.window.wayland.executable_available")
    def test_list_windows_no_backend(self, mock_avail):
        mock_avail.return_value = False
        provider = WaylandWindowProvider()
        with pytest.raises(WindowError, match="No Wayland backend"):
            provider.list_windows()


# ============================================================================
# WindowProvider ABC tests
# ============================================================================


def test_window_provider_is_abstract():
    """WindowProvider cannot be instantiated directly."""
    with pytest.raises(TypeError):
        WindowProvider()


# ============================================================================
# get_window_provider / detector tests
# ============================================================================


class TestGetWindowProvider:
    """Tests for get_window_provider."""

    @patch("peekxd.window.detector.detect_desktop")
    @patch("peekxd.window.x11.executable_available")
    @patch("peekxd.window.wayland.executable_available")
    def test_detects_x11_with_xdotool(self, mock_wl_avail, mock_x11_avail, mock_detect):
        mock_detect.return_value = DesktopEnvironment.X11
        mock_x11_avail.side_effect = lambda name: name == "xdotool"
        mock_wl_avail.return_value = False
        provider = get_window_provider()
        assert isinstance(provider, X11WindowProvider)

    @patch("peekxd.window.detector.detect_desktop")
    @patch("peekxd.window.x11.executable_available")
    @patch("peekxd.window.wayland.executable_available")
    def test_detects_wayland_with_wlrctl(self, mock_wl_avail, mock_x11_avail, mock_detect):
        mock_detect.return_value = DesktopEnvironment.WAYLAND
        mock_x11_avail.return_value = False
        mock_wl_avail.side_effect = lambda name: name == "wlrctl"
        provider = get_window_provider()
        assert isinstance(provider, WaylandWindowProvider)

    @patch("peekxd.window.detector.detect_desktop")
    @patch("peekxd.window.x11.executable_available")
    @patch("peekxd.window.wayland.executable_available")
    def test_raises_when_no_provider(self, mock_wl_avail, mock_x11_avail, mock_detect):
        mock_detect.return_value = DesktopEnvironment.UNKNOWN
        mock_x11_avail.return_value = False
        mock_wl_avail.return_value = False
        with pytest.raises(ProviderNotAvailableError):
            get_window_provider()

    @patch("peekxd.window.detector.detect_desktop")
    @patch("peekxd.window.x11.executable_available")
    @patch("peekxd.window.wayland.executable_available")
    def test_x11_fallback_to_wayland(self, mock_wl_avail, mock_x11_avail, mock_detect):
        """On X11, if xdotool is missing, fall back to Wayland provider."""
        mock_detect.return_value = DesktopEnvironment.X11
        mock_x11_avail.return_value = False
        mock_wl_avail.side_effect = lambda name: name == "swaymsg"
        provider = get_window_provider()
        assert isinstance(provider, WaylandWindowProvider)

    @patch("peekxd.window.detector.detect_desktop")
    @patch("peekxd.window.x11.executable_available")
    @patch("peekxd.window.wayland.executable_available")
    def test_wayland_fallback_to_x11(self, mock_wl_avail, mock_x11_avail, mock_detect):
        """On Wayland, if wlrctl/swaymsg is missing, fall back to X11 (XWayland)."""
        mock_detect.return_value = DesktopEnvironment.WAYLAND
        mock_x11_avail.side_effect = lambda name: name == "xdotool"
        mock_wl_avail.return_value = False
        provider = get_window_provider()
        assert isinstance(provider, X11WindowProvider)


# ============================================================================
# Module exports
# ============================================================================


def test_module_exports():
    """All expected classes are exported from peekxd.window."""
    from peekxd.window import (
        WindowProvider,
        X11WindowProvider,
        WaylandWindowProvider,
        get_window_provider,
    )

    assert issubclass(X11WindowProvider, WindowProvider)
    assert issubclass(WaylandWindowProvider, WindowProvider)
