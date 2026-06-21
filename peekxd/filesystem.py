"""Filesystem path navigation providers for desktop file managers."""

import subprocess
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Union

from peekxd.core.errors import ProviderNotAvailableError, peekxdError
from peekxd.core.utils import executable_available

PathLike = Union[str, Path]


class FilesystemProvider(ABC):
    """Abstract base class for safe desktop filesystem navigation."""

    @abstractmethod
    def open_path(self, path: PathLike) -> None:
        """Open a file or directory in the desktop's default handler."""
        ...

    @abstractmethod
    def select_path(self, path: PathLike) -> None:
        """Reveal a file path by opening its containing directory."""
        ...

    @property
    @abstractmethod
    def available(self) -> bool:
        """Whether this provider can navigate filesystem paths on this system."""
        ...


class _CommandFilesystemProvider(FilesystemProvider):
    """Base class for command-backed filesystem path providers."""

    command_name: str
    failure_label: str

    @property
    def available(self) -> bool:
        """Return True when the backing command is installed."""
        return executable_available(self.command_name)

    def open_path(self, path: PathLike) -> None:
        """Open an existing file or directory with the backing command."""
        target = self._existing_path(path)
        self._run_open(target)

    def select_path(self, path: PathLike) -> None:
        """Open the parent directory for files, or the directory itself."""
        target = self._existing_path(path)
        self._run_open(target if target.is_dir() else target.parent)

    def _run_open(self, path: Path) -> None:
        result = subprocess.run(
            [self.command_name, str(path)],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        if result.returncode != 0:
            stderr = result.stderr.strip() if result.stderr else ""
            raise peekxdError(f"{self.failure_label} failed", details={"stderr": stderr})

    @staticmethod
    def _existing_path(path: PathLike) -> Path:
        target = Path(path).expanduser().resolve()
        if not target.exists():
            raise peekxdError("Filesystem path does not exist", details={"path": str(target)})
        return target


class XdgOpenProvider(_CommandFilesystemProvider):
    """Filesystem provider backed by the ``xdg-open`` desktop launcher."""

    command_name = "xdg-open"
    failure_label = "xdg-open"


class GioProvider(_CommandFilesystemProvider):
    """Filesystem provider backed by ``gio open``."""

    command_name = "gio"
    failure_label = "gio open"

    def _run_open(self, path: Path) -> None:
        result = subprocess.run(
            ["gio", "open", str(path)],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        if result.returncode != 0:
            stderr = result.stderr.strip() if result.stderr else ""
            raise peekxdError("gio open failed", details={"stderr": stderr})


def get_filesystem_provider() -> FilesystemProvider:
    """Return the first available desktop filesystem navigation provider."""
    providers: list[FilesystemProvider] = [XdgOpenProvider(), GioProvider()]
    for provider in providers:
        if provider.available:
            return provider
    raise ProviderNotAvailableError("No filesystem provider available. Install: xdg-open or gio.")
