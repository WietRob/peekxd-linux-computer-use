"""Tests for desktop notification providers."""

import subprocess
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from peekxd.cli import cli
from peekxd.notification import (
    GdbusNotificationProvider,
    Notification,
    NotifySendProvider,
    get_notification_provider,
)


def _completed_process(stdout: str = "", stderr: str = "", returncode: int = 0):
    """Build a mock subprocess.CompletedProcess."""
    result = MagicMock(spec=subprocess.CompletedProcess)
    result.stdout = stdout
    result.stderr = stderr
    result.returncode = returncode
    return result


class TestNotifySendProvider:
    """Tests for notify-send-backed desktop notifications."""

    @patch("peekxd.notification.executable_available")
    def test_available_when_notify_send_installed(self, mock_available):
        mock_available.return_value = True

        assert NotifySendProvider().available is True

    @patch("peekxd.notification.executable_available")
    def test_not_available_when_notify_send_missing(self, mock_available):
        mock_available.return_value = False

        assert NotifySendProvider().available is False

    @patch("peekxd.notification.subprocess.run")
    def test_send_invokes_notify_send_with_body_urgency_and_timeout(self, mock_run):
        mock_run.return_value = _completed_process(returncode=0)

        NotifySendProvider().send(
            Notification(
                title="Build complete",
                body="All tests passed",
                urgency="critical",
                expire_timeout=5000,
            )
        )

        mock_run.assert_called_once_with(
            [
                "notify-send",
                "--urgency",
                "critical",
                "--expire-time",
                "5000",
                "Build complete",
                "All tests passed",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )

    @patch("peekxd.notification.subprocess.run")
    def test_send_raises_when_notify_send_fails(self, mock_run):
        mock_run.return_value = _completed_process(stderr="no display", returncode=1)

        try:
            NotifySendProvider().send(Notification(title="Build failed"))
        except Exception as exc:
            assert "notify-send notification failed" in str(exc)
        else:
            raise AssertionError("expected notify-send failure to raise")


class TestGdbusNotificationProvider:
    """Tests for direct D-Bus desktop notifications."""

    @patch("peekxd.notification.executable_available")
    def test_available_when_gdbus_installed(self, mock_available):
        mock_available.return_value = True

        assert GdbusNotificationProvider().available is True

    @patch("peekxd.notification.subprocess.run")
    def test_send_invokes_freedesktop_notifications(self, mock_run):
        mock_run.return_value = _completed_process(returncode=0)

        GdbusNotificationProvider().send(Notification(title="Done", body="Task finished"))

        args = mock_run.call_args.args[0]
        assert args[:6] == [
            "gdbus",
            "call",
            "--session",
            "--dest",
            "org.freedesktop.Notifications",
            "--object-path",
        ]
        assert "org.freedesktop.Notifications.Notify" in args
        assert "'Done'" in args
        assert "'Task finished'" in args


def test_get_notification_provider_returns_available_notify_send_provider():
    with patch("peekxd.notification.NotifySendProvider") as mock_provider_class:
        provider = MagicMock()
        provider.available = True
        mock_provider_class.return_value = provider

        assert get_notification_provider() is provider


def test_notify_cli_sends_desktop_notification():
    provider = MagicMock()

    with patch("peekxd.notification.get_notification_provider", return_value=provider):
        result = CliRunner().invoke(
            cli,
            [
                "notify",
                "Build complete",
                "--body",
                "All tests passed",
                "--urgency",
                "low",
                "--expire-timeout",
                "2500",
            ],
        )

    assert result.exit_code == 0, result.output
    provider.send.assert_called_once_with(
        Notification(
            title="Build complete",
            body="All tests passed",
            urgency="low",
            expire_timeout=2500,
        )
    )
    assert "Notification sent: Build complete" in result.output
