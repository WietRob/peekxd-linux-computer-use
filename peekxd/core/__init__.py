"""Core utilities for peekxd Linux."""

from .desktop import DesktopEnvironment, detect_desktop, is_x11, is_wayland
from .errors import (
    peekxdError,
    ProviderNotAvailableError,
    ScreenshotError,
    InputError,
    InspectionError,
    VisionError,
    ConfigurationError,
    PermissionDeniedError,
    WindowError,
)
from .utils import (
    find_executable,
    executable_available,
    run_command,
    expand_path,
    ensure_dir,
    get_config_dir,
    get_cache_dir,
)

__all__ = [
    "DesktopEnvironment",
    "detect_desktop",
    "is_x11",
    "is_wayland",
    "peekxdError",
    "ProviderNotAvailableError",
    "ScreenshotError",
    "InputError",
    "InspectionError",
    "VisionError",
    "ConfigurationError",
    "PermissionDeniedError",
    "WindowError",
    "find_executable",
    "executable_available",
    "run_command",
    "expand_path",
    "ensure_dir",
    "get_config_dir",
    "get_cache_dir",
]
