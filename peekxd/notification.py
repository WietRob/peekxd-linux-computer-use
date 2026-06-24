"""Desktop notification providers for non-blocking user feedback."""

import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal

from peekxd.core.errors import ProviderNotAvailableError, peekxdError
from peekxd.core.utils import executable_available

NotificationUrgency = Literal["low", "normal", "critical"]


@dataclass(frozen=True)
class Notification:
    """A desktop notification payload."""

    title: str
    body: str = ""
    urgency: NotificationUrgency = "normal"
    expire_timeout: int | None = None


class NotificationProvider(ABC):
    """Abstract base class for desktop notification providers."""

    @abstractmethod
    def send(self, notification: Notification) -> None:
        """Send a desktop notification."""
        ...

    @property
    @abstractmethod
    def available(self) -> bool:
        """Whether this provider can send notifications on the current system."""
        ...


class NotifySendProvider(NotificationProvider):
    """Notification provider backed by the ``notify-send`` command."""

    @property
    def available(self) -> bool:
        """Return True when notify-send is installed."""
        return executable_available("notify-send")

    def send(self, notification: Notification) -> None:
        """Send a notification through notify-send."""
        args = ["notify-send", "--urgency", notification.urgency]
        if notification.expire_timeout is not None:
            args.extend(["--expire-time", str(notification.expire_timeout)])
        args.append(notification.title)
        if notification.body:
            args.append(notification.body)

        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        if result.returncode != 0:
            stderr = result.stderr.strip() if result.stderr else ""
            raise peekxdError("notify-send notification failed", details={"stderr": stderr})


class GdbusNotificationProvider(NotificationProvider):
    """Notification provider backed by the Freedesktop Notifications D-Bus API."""

    @property
    def available(self) -> bool:
        """Return True when gdbus is installed."""
        return executable_available("gdbus")

    def send(self, notification: Notification) -> None:
        """Send a notification through ``org.freedesktop.Notifications``."""
        expire_timeout = (
            notification.expire_timeout if notification.expire_timeout is not None else -1
        )
        args = [
            "gdbus",
            "call",
            "--session",
            "--dest",
            "org.freedesktop.Notifications",
            "--object-path",
            "/org/freedesktop/Notifications",
            "--method",
            "org.freedesktop.Notifications.Notify",
            repr("peekxd"),
            "0",
            repr(""),
            repr(notification.title),
            repr(notification.body),
            "[]",
            "{}",
            str(expire_timeout),
        ]
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        if result.returncode != 0:
            stderr = result.stderr.strip() if result.stderr else ""
            raise peekxdError("gdbus notification failed", details={"stderr": stderr})


def get_notification_provider() -> NotificationProvider:
    """Return the first available desktop notification provider."""
    providers: list[NotificationProvider] = [NotifySendProvider(), GdbusNotificationProvider()]
    for provider in providers:
        if provider.available:
            return provider
    raise ProviderNotAvailableError(
        "No notification provider available. Install: notify-send or gdbus."
    )
