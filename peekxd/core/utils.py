"""Shared utilities for peekxd Linux."""

import shutil
import subprocess
import os
from pathlib import Path
from typing import Optional

from .errors import peekxdError


def find_executable(name: str) -> Optional[str]:
    """Find an executable in PATH."""
    return shutil.which(name)


def executable_available(name: str) -> bool:
    """Check if an executable is available in PATH."""
    return find_executable(name) is not None


def run_command(
    cmd: list[str],
    timeout: float = 30.0,
    capture_output: bool = True,
    check: bool = True,
    env: Optional[dict] = None,
) -> subprocess.CompletedProcess:
    """Run a shell command and return the result.

    Args:
        cmd: Command and arguments as list
        timeout: Maximum time to wait
        capture_output: Whether to capture stdout/stderr
        check: Whether to raise on non-zero exit
        env: Optional environment variables to add

    Returns:
        CompletedProcess instance

    Raises:
        peekxdError: If command fails or times out
    """
    merged_env = {**os.environ, **env} if env else None
    try:
        result = subprocess.run(
            cmd,
            timeout=timeout,
            capture_output=capture_output,
            text=True,
            check=False,
            env=merged_env,
        )
        if check and result.returncode != 0:
            stderr = result.stderr.strip() if result.stderr else ""
            stdout = result.stdout.strip() if result.stdout else ""
            raise peekxdError(
                f"Command failed (exit {result.returncode}): {' '.join(cmd)}",
                details={"stdout": stdout, "stderr": stderr, "command": cmd},
            )
        return result
    except subprocess.TimeoutExpired as exc:
        raise peekxdError(
            f"Command timed out after {timeout}s: {' '.join(cmd)}",
            details={"timeout": timeout},
        ) from exc
    except FileNotFoundError as exc:
        raise peekxdError(
            f"Command not found: {cmd[0]}",
            details={"command": cmd},
        ) from exc


def expand_path(path: str) -> Path:
    """Expand user home and resolve to absolute path."""
    return Path(os.path.expanduser(path)).expanduser().resolve()


def ensure_dir(path: str) -> Path:
    """Ensure directory exists, create if not."""
    p = expand_path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_config_dir() -> Path:
    """Get peekxd config directory (~/.peekxd)."""
    xdg_config = os.environ.get("XDG_CONFIG_HOME", "~/.config")
    return ensure_dir(f"{xdg_config}/peekxd")


def get_cache_dir() -> Path:
    """Get peekxd cache directory."""
    xdg_cache = os.environ.get("XDG_CACHE_HOME", "~/.cache")
    return ensure_dir(f"{xdg_cache}/peekxd")
