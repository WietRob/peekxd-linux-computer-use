"""Tests for display resolution providers."""

import subprocess
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from peekxd.cli import cli
from peekxd.display import Display, XrandrDisplayProvider, get_display_provider


def _completed_process(stdout: str = "", stderr: str = "", returncode: int = 0):
    """Build a mock subprocess.CompletedProcess."""
    result = MagicMock(spec=subprocess.CompletedProcess)
    result.stdout = stdout
    result.stderr = stderr
    result.returncode = returncode
    return result


class TestXrandrDisplayProvider:
    """Tests for xrandr-backed display queries."""

    @patch("peekxd.display.executable_available")
    def test_available_when_xrandr_installed(self, mock_available):
        mock_available.return_value = True

        assert XrandrDisplayProvider().available is True

    @patch("peekxd.display.executable_available")
    def test_not_available_when_xrandr_missing(self, mock_available):
        mock_available.return_value = False

        assert XrandrDisplayProvider().available is False

    @patch("peekxd.display.executable_available")
    @patch.object(XrandrDisplayProvider, "_run_xrandr")
    def test_list_displays_parses_connected_monitors(self, mock_run, mock_available):
        mock_available.return_value = True
        mock_run.return_value = _completed_process(
            stdout=(
                "Screen 0: minimum 8 x 8, current 3840 x 1080, maximum 32767 x 32767\n"
                "HDMI-1 connected primary 1920x1080+0+0 (normal left inverted right x axis y axis) 527mm x 296mm\n"
                "DP-1 connected 1920x1080+1920+0 (normal left inverted right x axis y axis) 527mm x 296mm\n"
                "DP-2 disconnected (normal left inverted right x axis y axis)\n"
            ),
            returncode=0,
        )

        displays = XrandrDisplayProvider().list_displays()

        assert displays == [
            Display(name="HDMI-1", width=1920, height=1080, x=0, y=0, primary=True),
            Display(name="DP-1", width=1920, height=1080, x=1920, y=0, primary=False),
        ]

    @patch("peekxd.display.executable_available")
    @patch.object(XrandrDisplayProvider, "_run_xrandr")
    def test_list_displays_ignores_disconnected_and_mode_lines(self, mock_run, mock_available):
        mock_available.return_value = True
        mock_run.return_value = _completed_process(
            stdout=(
                "eDP-1 connected primary 1366x768+0+0 (normal left inverted right x axis y axis) 309mm x 174mm\n"
                "   1366x768      60.00*+\n"
                "HDMI-1 disconnected (normal left inverted right x axis y axis)\n"
            ),
            returncode=0,
        )

        displays = XrandrDisplayProvider().list_displays()

        assert displays == [Display(name="eDP-1", width=1366, height=768, x=0, y=0, primary=True)]


def test_get_display_provider_returns_available_xrandr_provider():
    with patch("peekxd.display.XrandrDisplayProvider") as mock_provider_class:
        provider = MagicMock()
        provider.available = True
        mock_provider_class.return_value = provider

        assert get_display_provider() is provider


def test_display_list_cli_outputs_resolution_rows():
    provider = MagicMock()
    provider.list_displays.return_value = [
        Display(name="HDMI-1", width=1920, height=1080, x=0, y=0, primary=True),
        Display(name="DP-1", width=1280, height=1024, x=1920, y=0, primary=False),
    ]

    with patch("peekxd.display.get_display_provider", return_value=provider):
        result = CliRunner().invoke(cli, ["display", "list"])

    assert result.exit_code == 0, result.output
    assert "HDMI-1: 1920x1080+0+0 primary" in result.output
    assert "DP-1: 1280x1024+1920+0" in result.output
