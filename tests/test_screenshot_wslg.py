"""Tests for the WSLg/Windows-host screenshot provider."""

from pathlib import Path
from subprocess import TimeoutExpired
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from peekxd.core.errors import ScreenshotError
from peekxd.screenshot.windows_wsl import WindowsWslProvider


def _write_png(path: Path, size=(16, 12)) -> None:
    Image.new("RGBA", size, (255, 0, 0, 255)).save(path)


@patch("peekxd.screenshot.windows_wsl.executable_available")
@patch("peekxd.screenshot.windows_wsl.WindowsWslProvider._is_wsl")
def test_windows_wsl_missing_powershell_is_not_available(mock_is_wsl, mock_exec):
    """Provider is unavailable when PowerShell is missing in WSL."""
    mock_is_wsl.return_value = True
    mock_exec.side_effect = lambda name: name == "wslpath"

    assert WindowsWslProvider().available is False


@patch("peekxd.screenshot.windows_wsl.executable_available")
@patch("peekxd.screenshot.windows_wsl.WindowsWslProvider._is_wsl")
def test_windows_wsl_missing_wslpath_is_not_available(mock_is_wsl, mock_exec):
    """Provider is unavailable when wslpath is missing in WSL."""
    mock_is_wsl.return_value = True
    mock_exec.side_effect = lambda name: name == "powershell.exe"

    assert WindowsWslProvider().available is False


@patch("peekxd.screenshot.windows_wsl.executable_available", return_value=True)
@patch("peekxd.screenshot.windows_wsl.WindowsWslProvider._is_wsl", return_value=True)
def test_windows_wsl_capture_copies_windows_temp_png_to_requested_output(mock_is_wsl, mock_exec, tmp_path):
    """Successful capture copies the Windows temp PNG to the requested Linux output path."""
    source = tmp_path / "windows-temp.png"
    output = tmp_path / "requested" / "capture.png"
    _write_png(source)

    provider = WindowsWslProvider()
    with patch.object(provider, "_run_powershell_capture", return_value="C:\\Temp\\peekxd.png") as mock_capture, \
         patch.object(provider, "_windows_path_to_wsl", return_value=str(source)) as mock_to_wsl, \
         patch.object(provider, "_cleanup_windows_temp") as mock_cleanup:
        result = provider.capture_screen(str(output))

    assert result == str(output.resolve())
    assert output.exists()
    with Image.open(output) as im:
        assert im.size == (16, 12)
        assert im.mode == "RGBA"
    mock_capture.assert_called_once()
    mock_to_wsl.assert_called_once_with("C:\\Temp\\peekxd.png")
    mock_cleanup.assert_called_once_with("C:\\Temp\\peekxd.png")


@patch("peekxd.screenshot.windows_wsl.executable_available", return_value=True)
@patch("peekxd.screenshot.windows_wsl.WindowsWslProvider._is_wsl", return_value=True)
def test_windows_wsl_invalid_png_raises_clear_error(mock_is_wsl, mock_exec, tmp_path):
    """Invalid captured files are rejected instead of reported as successful screenshots."""
    source = tmp_path / "not-a-png.png"
    output = tmp_path / "capture.png"
    source.write_text("not png", encoding="utf-8")

    provider = WindowsWslProvider()
    with patch.object(provider, "_run_powershell_capture", return_value="C:\\Temp\\bad.png"), \
         patch.object(provider, "_windows_path_to_wsl", return_value=str(source)), \
         patch.object(provider, "_cleanup_windows_temp"):
        with pytest.raises(ScreenshotError, match="invalid PNG"):
            provider.capture_screen(str(output))


@patch("peekxd.screenshot.windows_wsl.executable_available", return_value=True)
@patch("peekxd.screenshot.windows_wsl.WindowsWslProvider._is_wsl", return_value=True)
def test_windows_wsl_timeout_raises_clear_error(mock_is_wsl, mock_exec, tmp_path):
    """PowerShell timeouts are surfaced as capture failures with context."""
    provider = WindowsWslProvider()
    with patch.object(provider, "_run_powershell_capture", side_effect=TimeoutExpired("powershell.exe", 30)):
        with pytest.raises(ScreenshotError, match="timed out"):
            provider.capture_screen(str(tmp_path / "capture.png"))
