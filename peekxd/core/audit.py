"""Audit trail and action logging for peekxd Linux.

Provides:
- Structured action logging with timestamps
- Session history
- Exportable audit trails (JSON)
- Action replay capability (log what happened, not undo)
"""

import json
import os
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .utils import get_cache_dir


@dataclass
class ActionEntry:
    """A single logged action."""

    action: str
    params: Dict[str, Any]
    result: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    step: int = 0
    session_id: str = ""
    error: Optional[str] = None
    screenshot_before: Optional[str] = None
    screenshot_after: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["time_iso"] = datetime.fromtimestamp(self.timestamp).isoformat()
        return d


class AuditLogger:
    """Structured audit logger for all peekxd actions.

    Every action is logged with full context for later inspection,
    debugging, or replay analysis.

    Example:
        logger = AuditLogger()
        logger.log_action("click", {"x": 100, "y": 200}, {"success": True})
        logger.export_json("/tmp/audit.json")
    """

    def __init__(self, session_id: Optional[str] = None):
        self.session_id = session_id or str(uuid.uuid4())[:8]
        self.actions: List[ActionEntry] = []
        self._start_time = time.time()
        self._screenshot_counter = 0

    def log_action(
        self,
        action: str,
        params: Dict[str, Any],
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        screenshot_before: Optional[str] = None,
        screenshot_after: Optional[str] = None,
        zone: Optional[str] = None,
        executed: Optional[bool] = None,
    ) -> ActionEntry:
        """Log a single action.

        Args:
            action: Action name.
            params: Action parameters.
            result: Action result dict.
            error: Error message if action failed.
            screenshot_before: Path to screenshot before action.
            screenshot_after: Path to screenshot after action.
            zone: Softbox zone (ghost, shadow, guided, direct).
            executed: Whether the action was actually executed.

        Returns:
            The created ActionEntry.
        """
        entry = ActionEntry(
            action=action,
            params=params,
            result=result or {},
            step=len(self.actions),
            session_id=self.session_id,
            error=error,
            screenshot_before=screenshot_before,
            screenshot_after=screenshot_after,
        )
        # Store zone and executed in result for audit trail
        if zone is not None:
            entry.result["zone"] = zone
        if executed is not None:
            entry.result["executed"] = executed
        self.actions.append(entry)
        return entry

    def log_screenshot(self, path: str, label: str = "") -> str:
        """Log a screenshot capture.

        Returns:
            The path (for convenience).
        """
        self.log_action(
            action="screenshot",
            params={"path": path, "label": label},
            result={"path": path},
        )
        return path

    def get_session_summary(self) -> Dict[str, Any]:
        """Get summary of current session."""
        elapsed = time.time() - self._start_time
        success_count = sum(1 for a in self.actions if a.error is None)
        error_count = len(self.actions) - success_count

        return {
            "session_id": self.session_id,
            "elapsed_seconds": round(elapsed, 2),
            "total_actions": len(self.actions),
            "successful": success_count,
            "failed": error_count,
            "actions": [a.to_dict() for a in self.actions],
        }

    def export_json(self, path: Optional[str] = None) -> str:
        """Export full audit trail to JSON.

        Args:
            path: Output file path. If None, uses cache dir.

        Returns:
            Path to exported file.
        """
        if path is None:
            audit_dir = get_cache_dir() / "audits"
            audit_dir.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = str(audit_dir / f"audit_{self.session_id}_{ts}.json")

        data = self.get_session_summary()
        with open(path, "w") as f:
            json.dump(data, f, indent=2, default=str)

        return path

    def recent_actions(self, n: int = 10) -> List[ActionEntry]:
        """Get the N most recent actions."""
        return self.actions[-n:]

    def find_actions(self, action_type: str) -> List[ActionEntry]:
        """Find all actions of a specific type."""
        return [a for a in self.actions if a.action == action_type]

    def format_readable(self) -> str:
        """Format audit trail as human-readable text."""
        lines = [f"=== Audit Session {self.session_id} ===", ""]
        for entry in self.actions:
            ts = datetime.fromtimestamp(entry.timestamp).strftime("%H:%M:%S")
            status = "OK" if entry.error is None else f"FAIL: {entry.error}"
            lines.append(f"[{ts}] Step {entry.step}: {entry.action} -> {status}")
            lines.append(f"       Params: {entry.params}")
            if entry.result:
                lines.append(f"       Result: {entry.result}")
        return "\n".join(lines)

    def get_next_screenshot_path(self, prefix: str = "audit") -> str:
        """Generate a unique screenshot path for this session."""
        self._screenshot_counter += 1
        cache = get_cache_dir() / "screenshots" / self.session_id
        cache.mkdir(parents=True, exist_ok=True)
        return str(cache / f"{prefix}_{self._screenshot_counter:04d}.png")


# Global audit logger
_global_logger: Optional[AuditLogger] = None


def get_logger() -> AuditLogger:
    """Get or create the global audit logger."""
    global _global_logger
    if _global_logger is None:
        _global_logger = AuditLogger()
    return _global_logger


def reset_logger():
    """Reset the global audit logger."""
    global _global_logger
    _global_logger = None
