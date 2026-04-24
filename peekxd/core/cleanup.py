"""Auto-cleanup for peekxd temporary files.

Manages temporary screenshot files to prevent /tmp accumulation.
Provides rotation policies and automatic cleanup.
"""

import glob
import os
import tempfile
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional

from .utils import get_cache_dir


# Prefixes that peekxd uses for temp files
_PEEKXD_PREFIXES = [
    "peekxd_",
    "peekxd_cap_",
    "peekxd_mark_",
    "peekxd_see_",
    "peekxd_screen_",
    "peekxd_window_",
    "peekxd_region_",
    "orch_see_",
    "analyze_",
    "find_",
    "findclick_",
    "typefield_",
    "click_find_",
    "mark_",
    "seq_capture_",
    "diff_cap_",
    "wait_",
    "fire_",
]

# Default: keep files younger than this
DEFAULT_MAX_AGE_HOURS = 24
# Default: keep at most this many files
DEFAULT_MAX_FILES = 100


class CleanupManager:
    """Manages automatic cleanup of peekxd temporary files.

    Example:
        cleanup = CleanupManager(max_age_hours=1, max_files=50)
        cleanup.run()  # Clean old files
        cleanup.schedule(interval_minutes=10)  # Auto-clean every 10 min
    """

    def __init__(
        self,
        max_age_hours: float = DEFAULT_MAX_AGE_HOURS,
        max_files: int = DEFAULT_MAX_FILES,
        directories: Optional[List[str]] = None,
    ):
        self.max_age_hours = max_age_hours
        self.max_files = max_files
        self.directories = directories or [tempfile.gettempdir(), str(get_cache_dir())]
        self._timer: Optional[threading.Timer] = None
        self._lock = threading.Lock()
        self.stats = {"cleaned": 0, "bytes_freed": 0, "runs": 0}

    def find_peekxd_files(self) -> List[Path]:
        """Find all peekxd temp files."""
        files = []
        for directory in self.directories:
            if not os.path.isdir(directory):
                continue
            for prefix in _PEEKXD_PREFIXES:
                pattern = os.path.join(directory, f"{prefix}*")
                for path in glob.glob(pattern):
                    if os.path.isfile(path):
                        files.append(Path(path))
        # Also find in cache dir
        cache = get_cache_dir()
        if cache.exists():
            for f in cache.glob("peekxd_*"):
                if f.is_file():
                    files.append(f)
        return sorted(files, key=lambda p: p.stat().st_mtime)

    def run(self) -> Dict[str, int]:
        """Run cleanup: remove old files, enforce max count.

        Returns:
            Stats dict with 'cleaned', 'bytes_freed', 'remaining'.
        """
        with self._lock:
            files = self.find_peekxd_files()
            cleaned = 0
            bytes_freed = 0
            now = time.time()
            max_age_sec = self.max_age_hours * 3600

            # Pass 1: remove files older than max_age
            for f in files:
                try:
                    age = now - f.stat().st_mtime
                    if age > max_age_sec:
                        size = f.stat().st_size
                        f.unlink()
                        cleaned += 1
                        bytes_freed += size
                except (OSError, PermissionError):
                    continue

            # Pass 2: if still over max_files, remove oldest
            files = self.find_peekxd_files()
            while len(files) > self.max_files:
                try:
                    f = files.pop(0)  # Oldest
                    size = f.stat().st_size
                    f.unlink()
                    cleaned += 1
                    bytes_freed += size
                except (OSError, PermissionError):
                    continue

            self.stats["cleaned"] += cleaned
            self.stats["bytes_freed"] += bytes_freed
            self.stats["runs"] += 1

            return {
                "cleaned": cleaned,
                "bytes_freed": bytes_freed,
                "remaining": len(self.find_peekxd_files()),
            }

    def schedule(self, interval_minutes: float = 30.0):
        """Schedule periodic automatic cleanup.

        Args:
            interval_minutes: Minutes between cleanup runs.
        """
        self._run_scheduled(interval_minutes)

    def _run_scheduled(self, interval: float):
        """Internal scheduled runner."""
        self.run()
        self._timer = threading.Timer(interval * 60, self._run_scheduled, args=(interval,))
        self._timer.daemon = True
        self._timer.start()

    def stop(self):
        """Stop scheduled cleanup."""
        if self._timer:
            self._timer.cancel()
            self._timer = None

    def __del__(self):
        self.stop()


def cleanup_now(
    max_age_hours: float = DEFAULT_MAX_AGE_HOURS,
    max_files: int = DEFAULT_MAX_FILES,
) -> Dict[str, int]:
    """One-shot cleanup function.

    Returns:
        Stats dict.
    """
    mgr = CleanupManager(max_age_hours=max_age_hours, max_files=max_files)
    return mgr.run()


# Global cleanup manager for module-level convenience
_global_cleanup: Optional[CleanupManager] = None


def start_auto_cleanup(interval_minutes: float = 30.0):
    """Start global auto-cleanup.

    Call this once at application startup.
    """
    global _global_cleanup
    if _global_cleanup is not None:
        return
    _global_cleanup = CleanupManager()
    _global_cleanup.schedule(interval_minutes)


def stop_auto_cleanup():
    """Stop global auto-cleanup."""
    global _global_cleanup
    if _global_cleanup:
        _global_cleanup.stop()
        _global_cleanup = None
