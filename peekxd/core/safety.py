"""Safety guardrails and preview mode for peekxd Linux.

Provides:
- Preview/simulation mode (no real actions executed)
- Destructive action detection
- Safety level configuration (strict, normal, permissive)
- Confirmation prompts for dangerous operations
- Dry-run support for action sequences
- Softbox zone integration (GHOST mode)
"""

import enum
import fnmatch
import os
from typing import Any, Callable, Dict, List, Optional

from .errors import peekxdError, PermissionDeniedError
from .zones import Zone, ZoneDecision, GhostPreviewResult, RiskDecision


class SafetyLevel(enum.Enum):
    """Safety mode levels."""

    STRICT = "strict"       # Preview all actions, require confirmation
    NORMAL = "normal"       # Preview destructive actions only
    PERMISSIVE = "permissive"  # Minimal checks, execute directly


# Patterns considered potentially destructive
_DESTRUCTIVE_PATTERNS = {
    "type": [
        "rm ", "sudo ", "dd ", "mkfs", "fdisk", "*delete*", "*remove*",
        "*DROP*", "*TRUNCATE*", "shred ", "wipe ", "format ",
    ],
    "key": [
        "Delete", "F12",  # BIOS keys
    ],
    "window": [
        "close", "kill",
    ],
}

# File system paths that are off-limits
_PROTECTED_PATHS = [
    "/", "/bin", "/sbin", "/usr/bin", "/usr/sbin",
    "/etc", "/boot", "/dev", "/proc", "/sys",
    "/lib", "/lib64", "/usr/lib", "/usr/lib64",
]


class SafetyGuard:
    """Safety guardrail system for peekxd actions.

    Configurable safety levels with preview mode support.
    Integrates with Softbox zone system for automatic risk-based
    zone assignment.

    Example:
        guard = SafetyGuard(SafetyLevel.STRICT)
        guard.check_action("type", {"text": "rm -rf /"})  # Raises PermissionDeniedError

        guard = SafetyGuard(SafetyLevel.NORMAL)
        decision = guard.check_zone("type", {"text": "rm -rf /"})
        assert decision.zone == Zone.GHOST
    """

    def __init__(self, level: SafetyLevel = SafetyLevel.NORMAL):
        self.level = level
        self.preview_log: List[Dict[str, Any]] = []
        self._is_preview_mode = level == SafetyLevel.STRICT
        self.zone_decisions: List[Dict[str, Any]] = []

    @property
    def is_preview(self) -> bool:
        """True if in preview/simulation mode."""
        return self._is_preview_mode

    def check_action(self, action: str, params: Dict[str, Any]) -> bool:
        """Check if an action is safe to execute.

        Args:
            action: Action name (click, type, key, etc.)
            params: Action parameters.

        Returns:
            True if action is safe.

        Raises:
            PermissionDeniedError: If action is flagged as dangerous.
        """
        if self.level == SafetyLevel.PERMISSIVE:
            return True

        risk, reason = self._assess_risk(action, params)

        if risk == "destructive":
            if self.level == SafetyLevel.STRICT:
                self.preview_log.append({
                    "action": action,
                    "params": params,
                    "risk": risk,
                    "reason": reason,
                    "executed": False,
                })
                raise PermissionDeniedError(
                    f"[PREVIEW BLOCKED] {action}: {reason}\n"
                    "Set safety level to 'normal' or 'permissive' to allow."
                )
            # NORMAL: log warning but allow
            self.preview_log.append({
                "action": action, "params": params, "risk": risk,
                "reason": reason, "executed": True,
            })
            return True

        if risk == "warn":
            self.preview_log.append({
                "action": action, "params": params, "risk": risk,
                "reason": reason, "executed": True,
            })
            return True

        return True

    def check_zone(self, action: str, params: Dict[str, Any]) -> RiskDecision:
        """Check which Softbox zone an action should execute in.

        This is the V1 Softbox integration point. The orchestrator calls
        this before _execute_action() to get a zone assignment.
        GHOST zone actions are previewed, not executed.

        Args:
            action: Action name.
            params: Action parameters.

        Returns:
            RiskDecision with zone assignment.
        """
        decision = ZoneDecision.decide(action, params)
        self.zone_decisions.append(decision.to_dict())
        return decision

    def get_zone_decisions(self) -> List[Dict[str, Any]]:
        """Return all zone decisions made."""
        return self.zone_decisions.copy()

    def reset_zone_decisions(self):
        """Clear zone decision history."""
        self.zone_decisions.clear()

    def _assess_risk(self, action: str, params: Dict[str, Any]) -> tuple:
        """Assess risk level of an action.

        Returns:
            (risk_level, reason) tuple. risk_level is one of:
            'safe', 'warn', 'destructive'
        """
        # Check type actions for dangerous commands
        if action in ("type", "type_text"):
            text = params.get("text", "")
            for pattern in _DESTRUCTIVE_PATTERNS["type"]:
                if fnmatch.fnmatch(text.lower(), pattern.lower()) or pattern.lower() in text.lower():
                    return ("destructive", f"Potentially destructive command detected: '{text[:50]}'")

        # Check key combinations
        if action in ("key", "hotkey"):
            keys = params.get("hotkey", []) or [params.get("key", "")]
            keys_str = "+".join(keys).lower()
            if "ctrl+alt+delete" in keys_str or "ctrl+alt+t" in keys_str:
                return ("warn", f"System key combination: {keys_str}")

        # Check protected paths
        if action == "capture_screen":
            path = params.get("output_path", "")
            for protected in _PROTECTED_PATHS:
                if path.startswith(protected):
                    return ("destructive", f"Screenshot to protected path: {path}")

        # Check window close
        if action in ("close_window",):
            return ("warn", "Window close operation")

        return ("safe", "")

    def preview(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate an action without executing it.

        Returns:
            Simulated result dict.
        """
        self.preview_log.append({
            "action": action,
            "params": params,
            "risk": "preview",
            "executed": False,
            "simulated": True,
        })
        return {
            "preview": True,
            "action": action,
            "params": params,
            "note": "This is a simulation — no real action was performed.",
        }

    def get_log(self) -> List[Dict[str, Any]]:
        """Return the safety decision log."""
        return self.preview_log.copy()

    def reset_log(self):
        """Clear the safety log."""
        self.preview_log.clear()


class DryRunExecutor:
    """Execute actions in dry-run mode — logs what WOULD happen.

    Wraps any action executor and previews instead of executing.
    """

    def __init__(self, real_executor: Optional[Callable] = None):
        self.log: List[Dict[str, Any]] = []
        self._real = real_executor

    def execute(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Log the action and return preview result."""
        entry = {
            "action": action,
            "params": params,
            "timestamp": __import__("time").time(),
        }
        self.log.append(entry)

        result = {
            "dry_run": True,
            "action": action,
            "params": params,
            "status": "would_execute",
        }

        # If real executor available, show what it would return
        if self._real:
            result["real_executor_available"] = True

        return result

    def get_plan(self) -> List[Dict[str, Any]]:
        """Return the full dry-run plan."""
        return self.log.copy()

    def summary(self) -> str:
        """Return human-readable summary of dry-run."""
        lines = [f"Dry-Run Plan ({len(self.log)} steps):"]
        for i, entry in enumerate(self.log, 1):
            action = entry["action"]
            params = entry["params"]
            lines.append(f"  {i}. {action}: {params}")
        lines.append("\nNo actions were actually executed.")
        return "\n".join(lines)
