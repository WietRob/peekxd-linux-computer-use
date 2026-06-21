"""Tests for desktop filesystem path navigation providers."""

import subprocess
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from peekxd.cli import cli
from peekxd.filesystem import GioProvider, XdgOpenProvider, get_filesystem_provider


def _completed_process(stdout: str = "", stderr: str = "", returncode: int = 0):
    """Build a mock subprocess.CompletedProcess."""
    result = MagicMock(spec=subprocess.CompletedProcess)
    result.stdout = stdout
    result.stderr = stderr
    result.returncode = returncode
    return result


class TestXdgOpenProvider:
    """Tests for xdg-open-backed filesystem navigation."""

    @patch("peekxd.filesystem.executable_available")
    def test_available_when_xdg_open_installed(self, mock_available):
        mock_available.return_value = True

        assert XdgOpenProvider().available is True

    @patch("peekxd.filesystem.executable_available")
    def test_not_available_when_xdg_open_missing(self, mock_available):
        mock_available.return_value = False

        assert XdgOpenProvider().available is False

    @patch("peekxd.filesystem.subprocess.run")
    def test_open_path_invokes_xdg_open_for_existing_path(self, mock_run, tmp_path):
        target = tmp_path / "notes.txt"
        target.write_text("hello", encoding="utf-8")
        mock_run.return_value = _completed_process(returncode=0)

        XdgOpenProvider().open_path(target)

        mock_run.assert_called_once_with(
            ["xdg-open", str(target)],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )

    @patch("peekxd.filesystem.subprocess.run")
    def test_select_path_opens_parent_directory_for_existing_file(self, mock_run, tmp_path):
        target = tmp_path / "notes.txt"
        target.write_text("hello", encoding="utf-8")
        mock_run.return_value = _completed_process(returncode=0)

        XdgOpenProvider().select_path(target)

        mock_run.assert_called_once_with(
            ["xdg-open", str(tmp_path)],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )

    @patch("peekxd.filesystem.subprocess.run")
    def test_open_path_raises_when_xdg_open_fails(self, mock_run, tmp_path):
        mock_run.return_value = _completed_process(stderr="no handler", returncode=3)

        try:
            XdgOpenProvider().open_path(tmp_path)
        except Exception as exc:
            assert "xdg-open failed" in str(exc)
        else:
            raise AssertionError("expected xdg-open failure to raise")


class TestGioProvider:
    """Tests for gio-backed filesystem navigation."""

    @patch("peekxd.filesystem.executable_available")
    def test_available_when_gio_installed(self, mock_available):
        mock_available.return_value = True

        assert GioProvider().available is True

    @patch("peekxd.filesystem.subprocess.run")
    def test_open_path_invokes_gio_open_for_existing_path(self, mock_run, tmp_path):
        target = tmp_path / "notes.txt"
        target.write_text("hello", encoding="utf-8")
        mock_run.return_value = _completed_process(returncode=0)

        GioProvider().open_path(target)

        mock_run.assert_called_once_with(
            ["gio", "open", str(target)],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )


def test_get_filesystem_provider_returns_available_xdg_open_provider():
    with patch("peekxd.filesystem.XdgOpenProvider") as mock_provider_class:
        provider = MagicMock()
        provider.available = True
        mock_provider_class.return_value = provider

        assert get_filesystem_provider() is provider


def test_file_open_cli_opens_path(tmp_path):
    provider = MagicMock()
    target = tmp_path / "notes.txt"
    target.write_text("hello", encoding="utf-8")

    with patch("peekxd.filesystem.get_filesystem_provider", return_value=provider):
        result = CliRunner().invoke(cli, ["file", "open", str(target)])

    assert result.exit_code == 0, result.output
    provider.open_path.assert_called_once_with(target)
    assert f"Opened: {target}" in result.output


def test_file_select_cli_selects_path(tmp_path):
    provider = MagicMock()
    target = tmp_path / "notes.txt"
    target.write_text("hello", encoding="utf-8")

    with patch("peekxd.filesystem.get_filesystem_provider", return_value=provider):
        result = CliRunner().invoke(cli, ["file", "select", str(target)])

    assert result.exit_code == 0, result.output
    provider.select_path.assert_called_once_with(target)
    assert f"Selected: {target}" in result.output
