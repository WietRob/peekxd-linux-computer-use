"""Tests for the screenshot module."""

import json
from pathlib import Path
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from peekxd.core.desktop import DesktopEnvironment
from peekxd.core.errors import peekxdError, ProviderNotAvailableError
from peekxd.screenshot import (
    GenericProvider,
    ScreenshotProvider,
    WaylandProvider,
    WindowsWslProvider,
    X11Provider,
    get_screenshot_provider,
)
from peekxd.screenshot.detector import get_screenshot_provider


# ---------------------------------------------------------------------------
# Provider availability tests
# ---------------------------------------------------------------------------

class TestProviderAvailability:
    """Test that each provider correctly reports availability."""

    @patch("peekxd.screenshot.x11.executable_available")
    def test_x11_available_with_import(self, mock_exec):
        """X11Provider.available is True when ImageMagick import exists."""
        mock_exec.side_effect = lambda name: name == "import"
        provider = X11Provider()
        assert provider.available is True

    @patch("peekxd.screenshot.x11.executable_available")
    def test_x11_available_with_xwd_and_convert(self, mock_exec):
        """X11Provider.available is True when the full xwd + convert chain exists."""
        mock_exec.side_effect = lambda name: name in ("xwd", "convert")
        provider = X11Provider()
        assert provider.available is True

    @patch("peekxd.screenshot.x11.executable_available")
    def test_x11_not_available_with_xwd_without_convert(self, mock_exec):
        """A bare xwd binary is not enough because PNG conversion would fail."""
        mock_exec.side_effect = lambda name: name == "xwd"
        provider = X11Provider()
        assert provider.available is False

    @patch("peekxd.screenshot.x11.executable_available")
    def test_x11_not_available(self, mock_exec):
        """X11Provider.available is False when neither tool exists."""
        mock_exec.return_value = False
        provider = X11Provider()
        assert provider.available is False

    @patch("peekxd.screenshot.wayland.executable_available")
    def test_wayland_available_with_grim(self, mock_exec):
        """WaylandProvider.available is True when grim exists."""
        mock_exec.side_effect = lambda name: name == "grim"
        provider = WaylandProvider()
        assert provider.available is True

    @patch("peekxd.screenshot.wayland.executable_available")
    def test_wayland_available_with_wayshot(self, mock_exec):
        """WaylandProvider.available is True when wayshot exists."""
        mock_exec.side_effect = lambda name: name == "wayshot"
        provider = WaylandProvider()
        assert provider.available is True

    @patch("peekxd.screenshot.wayland.executable_available")
    def test_wayland_not_available(self, mock_exec):
        """WaylandProvider.available is False when neither tool exists."""
        mock_exec.return_value = False
        provider = WaylandProvider()
        assert provider.available is False

    @patch("peekxd.screenshot.generic.executable_available")
    def test_generic_available_with_spectacle(self, mock_exec):
        """GenericProvider.available is True when spectacle exists."""
        mock_exec.side_effect = lambda name: name == "spectacle"
        provider = GenericProvider()
        assert provider.available is True

    @patch("peekxd.screenshot.generic.executable_available")
    def test_generic_available_with_flameshot(self, mock_exec):
        """GenericProvider.available is True when flameshot exists."""
        mock_exec.side_effect = lambda name: name == "flameshot"
        provider = GenericProvider()
        assert provider.available is True

    @patch("peekxd.screenshot.generic.executable_available")
    def test_generic_available_with_gnome_screenshot(self, mock_exec):
        """GenericProvider.available is True when gnome-screenshot exists."""
        mock_exec.side_effect = lambda name: name == "gnome-screenshot"
        provider = GenericProvider()
        assert provider.available is True

    @patch("peekxd.screenshot.generic.executable_available")
    def test_generic_not_available(self, mock_exec):
        """GenericProvider.available is False when no generic tool exists."""
        mock_exec.return_value = False
        provider = GenericProvider()
        assert provider.available is False

    @patch("peekxd.screenshot.windows_wsl.executable_available")
    @patch("peekxd.screenshot.windows_wsl.WindowsWslProvider._is_wsl")
    def test_windows_wsl_available_in_wsl_with_powershell(self, mock_is_wsl, mock_exec):
        """WindowsWslProvider.available is True in WSL with powershell.exe and wslpath."""
        mock_is_wsl.return_value = True
        mock_exec.side_effect = lambda name: name in ("powershell.exe", "wslpath")
        provider = WindowsWslProvider()
        assert provider.available is True

    @patch("peekxd.screenshot.windows_wsl.executable_available")
    @patch("peekxd.screenshot.windows_wsl.WindowsWslProvider._is_wsl")
    def test_windows_wsl_not_available_outside_wsl(self, mock_is_wsl, mock_exec):
        """WindowsWslProvider.available is False outside WSL."""
        mock_is_wsl.return_value = False
        mock_exec.return_value = True
        provider = WindowsWslProvider()
        assert provider.available is False


# ---------------------------------------------------------------------------
# get_screenshot_provider detection tests
# ---------------------------------------------------------------------------

class TestGetScreenshotProvider:
    """Test auto-detection of the best screenshot provider."""

    @patch("peekxd.screenshot.detector.detect_desktop")
    @patch("peekxd.screenshot.windows_wsl.WindowsWslProvider.available", new_callable=PropertyMock)
    @patch("peekxd.screenshot.x11.executable_available")
    def test_detects_x11_provider_on_x11(self, mock_exec, mock_wsl_available, mock_desktop):
        """When on X11 with import available, returns X11Provider."""
        mock_desktop.return_value = DesktopEnvironment.X11
        mock_wsl_available.return_value = False
        mock_exec.return_value = True  # import available
        provider = get_screenshot_provider()
        assert isinstance(provider, X11Provider)

    @patch("peekxd.screenshot.detector.detect_desktop")
    @patch("peekxd.screenshot.windows_wsl.WindowsWslProvider.available", new_callable=PropertyMock)
    @patch("peekxd.screenshot.wayland.executable_available")
    @patch("peekxd.screenshot.x11.executable_available")
    def test_detects_wayland_provider_on_wayland(self, mock_x11, mock_wl, mock_wsl_available, mock_desktop):
        """When on Wayland with grim available, returns WaylandProvider."""
        mock_desktop.return_value = DesktopEnvironment.WAYLAND
        mock_wsl_available.return_value = False
        mock_x11.return_value = False
        mock_wl.side_effect = lambda name: name == "grim"
        provider = get_screenshot_provider()
        assert isinstance(provider, WaylandProvider)

    @patch("peekxd.screenshot.detector.detect_desktop")
    @patch("peekxd.screenshot.windows_wsl.WindowsWslProvider.available", new_callable=PropertyMock)
    def test_prefers_windows_wsl_provider_in_wslg(self, mock_wsl_available, mock_desktop):
        """WSLg prefers Windows host capture over advertised Wayland/X11 paths."""
        mock_desktop.return_value = DesktopEnvironment.WAYLAND
        mock_wsl_available.return_value = True
        provider = get_screenshot_provider()
        assert isinstance(provider, WindowsWslProvider)

    @patch("peekxd.screenshot.detector.detect_desktop")
    @patch("peekxd.screenshot.windows_wsl.WindowsWslProvider.available", new_callable=PropertyMock)
    @patch("peekxd.screenshot.generic.executable_available")
    @patch("peekxd.screenshot.x11.executable_available")
    def test_falls_back_to_generic_on_x11(self, mock_x11, mock_gen, mock_wsl_available, mock_desktop):
        """When on X11 with no X11 tools, falls back to GenericProvider."""
        mock_desktop.return_value = DesktopEnvironment.X11
        mock_wsl_available.return_value = False
        mock_x11.return_value = False  # no import or xwd
        mock_gen.side_effect = lambda name: name == "spectacle"
        provider = get_screenshot_provider()
        assert isinstance(provider, GenericProvider)

    @patch("peekxd.screenshot.detector.detect_desktop")
    @patch("peekxd.screenshot.windows_wsl.WindowsWslProvider.available", new_callable=PropertyMock)
    @patch("peekxd.screenshot.generic.executable_available")
    @patch("peekxd.screenshot.wayland.executable_available")
    @patch("peekxd.screenshot.x11.executable_available")
    def test_unknown_desktop_tries_all_providers(self, mock_x11, mock_wl, mock_gen, mock_wsl_available, mock_desktop):
        """When desktop is unknown, tries all providers in order."""
        mock_desktop.return_value = DesktopEnvironment.UNKNOWN
        mock_wsl_available.return_value = False
        mock_x11.return_value = False
        mock_wl.return_value = False
        mock_gen.side_effect = lambda name: name == "flameshot"
        provider = get_screenshot_provider()
        assert isinstance(provider, GenericProvider)

    @patch("peekxd.screenshot.detector.detect_desktop")
    @patch("peekxd.screenshot.windows_wsl.WindowsWslProvider.available", new_callable=PropertyMock)
    @patch("peekxd.screenshot.generic.executable_available")
    @patch("peekxd.screenshot.wayland.executable_available")
    @patch("peekxd.screenshot.x11.executable_available")
    def test_raises_when_no_provider_available(self, mock_x11, mock_wl, mock_gen, mock_wsl_available, mock_desktop):
        """When no tools are available, raises ProviderNotAvailableError."""
        mock_desktop.return_value = DesktopEnvironment.UNKNOWN
        mock_wsl_available.return_value = False
        mock_x11.return_value = False
        mock_wl.return_value = False
        mock_gen.return_value = False
        with pytest.raises(ProviderNotAvailableError):
            get_screenshot_provider()


# ---------------------------------------------------------------------------
# Capture method tests with mocked run_command
# ---------------------------------------------------------------------------

class TestX11Capture:
    """Test X11Provider capture methods."""

    @patch("peekxd.screenshot.x11.executable_available")
    @patch("peekxd.screenshot.x11.run_command")
    def test_capture_screen_with_import(self, mock_run, mock_exec):
        """capture_screen calls import with correct args."""
        mock_exec.side_effect = lambda name: name in ("import", "xrandr")
        mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)

        provider = X11Provider()
        result = provider.capture_screen("/tmp/test.png", display=0)
        assert result == "/tmp/test.png"
        mock_run.assert_any_call(
            ["import", "-window", "root", "-display", ":0", "/tmp/test.png"],
        )

    @patch("peekxd.screenshot.x11.executable_available")
    @patch("peekxd.screenshot.x11.run_command")
    def test_capture_screen_falls_back_to_xwd_when_import_fails(self, mock_run, mock_exec, tmp_path):
        """X11 capture is tool-agnostic: a broken import binary does not block xwd+convert."""
        output = str(tmp_path / "test.png")
        mock_exec.side_effect = lambda name: name in ("import", "xwd", "convert")
        mock_run.side_effect = [RuntimeError("import cannot read root"), MagicMock(), MagicMock()]

        result = X11Provider().capture_screen(output, display=0)

        assert result == output
        assert mock_run.call_args_list[0].args[0] == ["import", "-window", "root", "-display", ":0", output]
        assert mock_run.call_args_list[1].args[0][0:4] == ["xwd", "-root", "-display", ":0"]
        assert mock_run.call_args_list[2].args[0] == ["convert", "/tmp/peekxd_screen.xwd", output]

    @patch("peekxd.screenshot.x11.executable_available")
    @patch("peekxd.screenshot.x11.run_command")
    def test_capture_window_with_window_id(self, mock_run, mock_exec):
        """capture_window uses given window_id."""
        mock_exec.side_effect = lambda name: name in ("import", "xrandr")
        mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)

        provider = X11Provider()
        result = provider.capture_window("/tmp/test.png", window_id="0x12345")
        assert result == "/tmp/test.png"
        mock_run.assert_any_call(
            ["import", "-window", "0x12345", "/tmp/test.png"],
        )

    @patch("peekxd.screenshot.x11.executable_available")
    @patch("peekxd.screenshot.x11.run_command")
    def test_capture_region(self, mock_run, mock_exec):
        """capture_region calls import with crop geometry."""
        mock_exec.side_effect = lambda name: name in ("import", "xrandr")
        mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)

        provider = X11Provider()
        result = provider.capture_region("/tmp/test.png", x=10, y=20, width=300, height=200)
        assert result == "/tmp/test.png"
        mock_run.assert_any_call(
            ["import", "-crop", "300x200+10+20", "/tmp/test.png"],
        )

    @patch("peekxd.screenshot.x11.executable_available")
    def test_capture_screen_raises_when_no_tools(self, mock_exec):
        """capture_screen raises ScreenshotError when no tools available."""
        mock_exec.return_value = False
        provider = X11Provider()
        with pytest.raises(peekxdError):
            provider.capture_screen("/tmp/test.png")


class TestWaylandCapture:
    """Test WaylandProvider capture methods."""

    @patch("peekxd.screenshot.wayland.executable_available")
    @patch("peekxd.screenshot.wayland.run_command")
    def test_capture_screen_with_grim(self, mock_run, mock_exec):
        """capture_screen calls grim with correct args."""
        mock_exec.side_effect = lambda name: name in ("grim", "swaymsg")
        mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)

        provider = WaylandProvider()
        result = provider.capture_screen("/tmp/test.png")
        assert result == "/tmp/test.png"
        mock_run.assert_any_call(["grim", "/tmp/test.png"])

    @patch("peekxd.screenshot.wayland.executable_available")
    @patch("peekxd.screenshot.wayland.run_command")
    def test_capture_screen_falls_back_to_wayshot_when_grim_fails(self, mock_run, mock_exec):
        """Wayland capture is compositor/tool agnostic when multiple tools exist."""
        mock_exec.side_effect = lambda name: name in ("grim", "wayshot")
        mock_run.side_effect = [RuntimeError("grim unsupported compositor"), MagicMock(stdout="", stderr="", returncode=0)]

        result = WaylandProvider().capture_screen("/tmp/test.png")

        assert result == "/tmp/test.png"
        assert mock_run.call_args_list[0].args[0] == ["grim", "/tmp/test.png"]
        assert mock_run.call_args_list[1].args[0] == ["wayshot", "-f", "/tmp/test.png"]

    @patch("peekxd.screenshot.wayland.executable_available")
    @patch("peekxd.screenshot.wayland.run_command")
    def test_capture_screen_with_wayshot(self, mock_run, mock_exec):
        """capture_screen calls wayshot when grim is not available."""
        mock_exec.side_effect = lambda name: name in ("wayshot", "swaymsg")
        mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)

        provider = WaylandProvider()
        result = provider.capture_screen("/tmp/test.png")
        assert result == "/tmp/test.png"
        mock_run.assert_any_call(["wayshot", "-f", "/tmp/test.png"])

    @patch("peekxd.screenshot.wayland.executable_available")
    @patch("peekxd.screenshot.wayland.run_command")
    def test_capture_region(self, mock_run, mock_exec):
        """capture_region calls grim with geometry string."""
        mock_exec.side_effect = lambda name: name in ("grim", "swaymsg")
        mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)

        provider = WaylandProvider()
        result = provider.capture_region("/tmp/test.png", x=10, y=20, width=300, height=200)
        assert result == "/tmp/test.png"
        mock_run.assert_any_call(["grim", "-g", "10,20 300x200", "/tmp/test.png"])

    @patch("peekxd.screenshot.wayland.executable_available")
    def test_capture_screen_raises_when_no_tools(self, mock_exec):
        """capture_screen raises ScreenshotError when no tools available."""
        mock_exec.return_value = False
        provider = WaylandProvider()
        with pytest.raises(peekxdError):
            provider.capture_screen("/tmp/test.png")


class TestGenericCapture:
    """Test GenericProvider capture methods."""

    @patch("peekxd.screenshot.generic.executable_available")
    @patch("peekxd.screenshot.generic.run_command")
    def test_capture_screen_with_spectacle(self, mock_run, mock_exec):
        """capture_screen calls spectacle with correct args."""
        mock_exec.side_effect = lambda name: name == "spectacle"
        mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)

        provider = GenericProvider()
        result = provider.capture_screen("/tmp/test.png")
        assert result == "/tmp/test.png"
        mock_run.assert_any_call(["spectacle", "-b", "-o", "/tmp/test.png"])

    @patch("peekxd.screenshot.generic.executable_available")
    @patch("peekxd.screenshot.generic.run_command")
    def test_capture_screen_with_flameshot(self, mock_run, mock_exec):
        """capture_screen calls flameshot when spectacle is not available."""
        mock_exec.side_effect = lambda name: name == "flameshot"
        mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)

        provider = GenericProvider()
        result = provider.capture_screen("/tmp/test.png")
        assert result == "/tmp/test.png"
        mock_run.assert_any_call(["flameshot", "full", "-p", "/tmp/test.png"])

    @patch("peekxd.screenshot.generic.executable_available")
    @patch("peekxd.screenshot.generic.run_command")
    def test_capture_window_with_spectacle(self, mock_run, mock_exec):
        """capture_window calls spectacle -a (active window)."""
        mock_exec.side_effect = lambda name: name == "spectacle"
        mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)

        provider = GenericProvider()
        result = provider.capture_window("/tmp/test.png")
        assert result == "/tmp/test.png"
        mock_run.assert_any_call(["spectacle", "-b", "-a", "-o", "/tmp/test.png"])

    @patch("peekxd.screenshot.generic.executable_available")
    @patch("peekxd.screenshot.generic.run_command")
    def test_capture_region_with_spectacle(self, mock_run, mock_exec):
        """capture_region calls spectacle -r (region)."""
        mock_exec.side_effect = lambda name: name == "spectacle"
        mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)

        provider = GenericProvider()
        result = provider.capture_region("/tmp/test.png", x=0, y=0, width=100, height=100)
        assert result == "/tmp/test.png"
        mock_run.assert_any_call(["spectacle", "-b", "-r", "-o", "/tmp/test.png"])

    @patch("peekxd.screenshot.generic.executable_available")
    def test_capture_screen_raises_when_no_tools(self, mock_exec):
        """capture_screen raises ScreenshotError when no tools available."""
        mock_exec.return_value = False
        provider = GenericProvider()
        with pytest.raises(peekxdError):
            provider.capture_screen("/tmp/test.png")


# ---------------------------------------------------------------------------
# list_windows / list_screens return type tests
# ---------------------------------------------------------------------------

class TestListMethods:
    """Test that list_windows and list_screens return the correct types."""

    @patch("peekxd.screenshot.x11.executable_available")
    @patch("peekxd.screenshot.x11.run_command")
    def test_x11_list_screens_returns_list_of_dicts(self, mock_run, mock_exec):
        """X11Provider.list_screens returns List[Dict]."""
        mock_exec.side_effect = lambda name: name == "xrandr"
        mock_run.return_value = MagicMock(
            stdout="0: +*DP-1 1920/527x1080/296+0+0  DP-1\n1: +HDMI-1 1080/508x1920/286+1920+0  HDMI-1",
            stderr="",
            returncode=0,
        )

        provider = X11Provider()
        screens = provider.list_screens()
        assert isinstance(screens, list)
        for screen in screens:
            assert isinstance(screen, dict)
            assert "name" in screen

    @patch("peekxd.screenshot.x11.executable_available")
    @patch("peekxd.screenshot.x11.run_command")
    def test_x11_list_windows_returns_list_of_dicts(self, mock_run, mock_exec):
        """X11Provider.list_windows returns List[Dict]."""
        mock_exec.side_effect = lambda name: name == "xdotool"
        mock_run.side_effect = [
            MagicMock(stdout="12345\n67890", stderr="", returncode=0),
            MagicMock(stdout="Terminal", stderr="", returncode=0),
            MagicMock(stdout="Browser", stderr="", returncode=0),
        ]

        provider = X11Provider()
        windows = provider.list_windows()
        assert isinstance(windows, list)
        for window in windows:
            assert isinstance(window, dict)
            assert "id" in window

    @patch("peekxd.screenshot.wayland.executable_available")
    @patch("peekxd.screenshot.wayland.run_command")
    def test_wayland_list_screens_returns_list_of_dicts(self, mock_run, mock_exec):
        """WaylandProvider.list_screens returns List[Dict]."""
        mock_exec.side_effect = lambda name: name == "swaymsg"
        mock_run.return_value = MagicMock(
            stdout=json.dumps([
                {
                    "name": "eDP-1",
                    "active": True,
                    "primary": True,
                    "rect": {"x": 0, "y": 0, "width": 1920, "height": 1080},
                },
            ]),
            stderr="",
            returncode=0,
        )

        provider = WaylandProvider()
        screens = provider.list_screens()
        assert isinstance(screens, list)
        assert len(screens) == 1
        assert screens[0]["name"] == "eDP-1"
        assert screens[0]["width"] == 1920
        assert screens[0]["height"] == 1080

    @patch("peekxd.screenshot.wayland.executable_available")
    @patch("peekxd.screenshot.wayland.run_command")
    def test_wayland_list_windows_returns_list_of_dicts(self, mock_run, mock_exec):
        """WaylandProvider.list_windows returns List[Dict]."""
        mock_exec.side_effect = lambda name: name == "swaymsg"
        mock_run.return_value = MagicMock(
            stdout=json.dumps({
                "id": 1,
                "nodes": [
                    {
                        "id": 2,
                        "app_id": "terminal",
                        "name": "Terminal Window",
                        "window_properties": {"title": "Terminal Window", "class": "Terminal"},
                    },
                ],
                "floating_nodes": [],
            }),
            stderr="",
            returncode=0,
        )

        provider = WaylandProvider()
        windows = provider.list_windows()
        assert isinstance(windows, list)
        for window in windows:
            assert isinstance(window, dict)
            assert "id" in window

    @patch("peekxd.screenshot.generic.executable_available")
    def test_generic_list_windows_returns_empty_list(self, mock_exec):
        """GenericProvider.list_windows returns empty list (not supported)."""
        mock_exec.side_effect = lambda name: name == "spectacle"
        provider = GenericProvider()
        windows = provider.list_windows()
        assert windows == []

    @patch("peekxd.screenshot.generic.executable_available")
    def test_generic_list_screens_returns_empty_list(self, mock_exec):
        """GenericProvider.list_screens returns empty list (not supported)."""
        mock_exec.side_effect = lambda name: name == "spectacle"
        provider = GenericProvider()
        screens = provider.list_screens()
        assert screens == []


# ---------------------------------------------------------------------------
# Module import / export tests
# ---------------------------------------------------------------------------

class TestModuleExports:
    """Test that the screenshot module exports all expected symbols."""

    def test_base_is_abstract(self):
        """ScreenshotProvider cannot be instantiated directly."""
        with pytest.raises(TypeError):
            ScreenshotProvider()

    def test_all_classes_importable(self):
        """All provider classes can be imported from the package."""
        from peekxd.screenshot import (
            GenericProvider,
            ScreenshotProvider,
            WaylandProvider,
            X11Provider,
            get_screenshot_provider,
        )

        assert issubclass(X11Provider, ScreenshotProvider)
        assert issubclass(WaylandProvider, ScreenshotProvider)
        assert issubclass(GenericProvider, ScreenshotProvider)

    def test_detector_function_exists(self):
        """get_screenshot_provider function is importable."""
        from peekxd.screenshot.detector import get_screenshot_provider

        assert callable(get_screenshot_provider)
