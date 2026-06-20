"""Display resolution providers for read-only monitor queries."""

import re
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List

from peekxd.core.errors import ProviderNotAvailableError, peekxdError
from peekxd.core.utils import executable_available


@dataclass(frozen=True)
class Display:
    """A connected display and its desktop-space geometry."""

    name: str
    width: int
    height: int
    x: int = 0
    y: int = 0
    primary: bool = False


class DisplayProvider(ABC):
    """Abstract base class for read-only display resolution providers."""

    @abstractmethod
    def list_displays(self) -> List[Display]:
        """Return connected displays with resolution and desktop offset."""
        ...

    @property
    @abstractmethod
    def available(self) -> bool:
        """Whether this provider can query displays on the current system."""
        ...


class XrandrDisplayProvider(DisplayProvider):
    """Display provider backed by the X11 ``xrandr --query`` command."""

    _CONNECTED_RE = re.compile(
        r"^(?P<name>\S+)\s+connected\s+(?P<primary>primary\s+)?"
        r"(?P<width>\d+)x(?P<height>\d+)\+(?P<x>-?\d+)\+(?P<y>-?\d+)"
    )

    @property
    def available(self) -> bool:
        """Return True when xrandr is installed."""
        return executable_available("xrandr")

    def list_displays(self) -> List[Display]:
        """List connected X11 displays parsed from xrandr output."""
        result = self._run_xrandr()
        if result.returncode != 0:
            stderr = result.stderr.strip() if result.stderr else ""
            raise peekxdError("xrandr display query failed", details={"stderr": stderr})
        return self._parse_xrandr(result.stdout)

    def _run_xrandr(self) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["xrandr", "--query"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )

    @classmethod
    def _parse_xrandr(cls, output: str) -> List[Display]:
        displays: List[Display] = []
        for line in output.splitlines():
            match = cls._CONNECTED_RE.match(line.strip())
            if not match:
                continue
            displays.append(
                Display(
                    name=match.group("name"),
                    width=int(match.group("width")),
                    height=int(match.group("height")),
                    x=int(match.group("x")),
                    y=int(match.group("y")),
                    primary=bool(match.group("primary")),
                )
            )
        return displays


class WlrrandrDisplayProvider(DisplayProvider):
    """Display provider backed by ``wlr-randr`` for wlroots compositors."""

    _MODE_RE = re.compile(r"(?P<width>\d+)x(?P<height>\d+) px")
    _POSITION_RE = re.compile(r"Position:\s+(?P<x>-?\d+),(?P<y>-?\d+)")

    @property
    def available(self) -> bool:
        """Return True when wlr-randr is installed."""
        return executable_available("wlr-randr")

    def list_displays(self) -> List[Display]:
        """List connected Wayland displays parsed from wlr-randr output."""
        result = self._run_wlrrandr()
        if result.returncode != 0:
            stderr = result.stderr.strip() if result.stderr else ""
            raise peekxdError("wlr-randr display query failed", details={"stderr": stderr})
        return self._parse_wlrrandr(result.stdout)

    def _run_wlrrandr(self) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["wlr-randr"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )

    @classmethod
    def _parse_wlrrandr(cls, output: str) -> List[Display]:
        displays: List[Display] = []
        current_name: str | None = None
        width = height = x = y = 0
        enabled = False
        primary = False

        def flush() -> None:
            if current_name and enabled and width and height:
                displays.append(Display(current_name, width, height, x, y, primary))

        for raw_line in output.splitlines():
            line = raw_line.rstrip()
            if line and not raw_line.startswith(" "):
                flush()
                current_name = line.split()[0]
                width = height = x = y = 0
                enabled = True
                primary = "(primary)" in line
                continue
            stripped = line.strip()
            if stripped == "Enabled: no":
                enabled = False
            mode_match = cls._MODE_RE.search(stripped)
            if mode_match and "current" in stripped:
                width = int(mode_match.group("width"))
                height = int(mode_match.group("height"))
            position_match = cls._POSITION_RE.search(stripped)
            if position_match:
                x = int(position_match.group("x"))
                y = int(position_match.group("y"))
        flush()
        return displays


def get_display_provider() -> DisplayProvider:
    """Return the first viable read-only display provider.

    Tries each available provider and falls back to the next one if a
    provider is installed but not operational (e.g. xrandr present on a
    Wayland-only session).
    """
    providers: list[DisplayProvider] = [XrandrDisplayProvider(), WlrrandrDisplayProvider()]
    last_error: Exception | None = None
    for provider in providers:
        if provider.available:
            try:
                provider.list_displays()
                return provider
            except Exception as exc:
                last_error = exc
                continue
    msg = "No display provider available. Install: xrandr or wlr-randr."
    if last_error:
        msg += f" Last error: {last_error}"
    raise ProviderNotAvailableError(msg)
