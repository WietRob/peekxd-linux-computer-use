"""Shadow recorder for peekxd Linux (Softbox Shadow Mode V2).

Provides before/after screenshot capture, comparison, and structured
audit metadata for actions executed in SHADOW zone.

Key design:
- ShadowRecorder does NOT perform any desktop actions itself.
- It wraps an action_callable: before screenshot → call action → after screenshot.
- Screenshot failures are captured in ShadowResult.error, never crash the action.
- Comparison is byte-level or via basic file comparison.
"""

import os
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional


@dataclass
class ShadowSnapshot:
    """A single screenshot snapshot with metadata."""

    timestamp: str
    screenshot_path: Optional[str]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "screenshot_path": self.screenshot_path,
            "metadata": self.metadata,
        }


@dataclass
class ShadowResult:
    """Result of a shadow-mode action execution.

    Contains before/after snapshots, comparison result, and any errors.
    """

    before_snapshot: Optional[ShadowSnapshot] = None
    after_snapshot: Optional[ShadowSnapshot] = None
    changed: Optional[bool] = None
    diff_summary: str = ""
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_before": self.before_snapshot.to_dict() if self.before_snapshot else None,
            "snapshot_after": self.after_snapshot.to_dict() if self.after_snapshot else None,
            "changed": self.changed,
            "diff_summary": self.diff_summary,
            "error": self.error,
            "metadata": self.metadata,
        }


class ShadowRecorder:
    """Records before/after snapshots for shadow-mode actions.

    Does NOT perform desktop actions — only wraps an action_callable with
    screenshot capture before and after execution.

    Example:
        recorder = ShadowRecorder(capture_fn=my_screenshot_capture)
        result, shadow = recorder.wrap(
            action_callable=lambda: execute_action("type", {"text": "hello"}),
            action="type",
            params={"text": "hello"},
            screen_state={"path": "/tmp/current.png"},
        )
    """

    def __init__(
        self,
        capture_fn: Optional[Callable[[str], None]] = None,
        get_screenshot_path_fn: Optional[Callable[[], str]] = None,
    ):
        """Initialize the shadow recorder.

        Args:
            capture_fn: Function that takes a path and saves a screenshot there.
                        Signature: capture_fn(path: str) -> None
            get_screenshot_path_fn: Function that returns a unique screenshot path.
                                    Signature: get_screenshot_path_fn() -> str
        """
        self._capture = capture_fn
        self._get_path = get_screenshot_path_fn

    def snapshot_before(
        self, screen_state: Optional[Dict[str, Any]]
    ) -> Optional[ShadowSnapshot]:
        """Take a snapshot before the action.

        Uses screen_state["path"] if available, or captures a fresh screenshot.

        Args:
            screen_state: Current screen state dict with optional "path" key.

        Returns:
            ShadowSnapshot or None if no screenshot could be taken.
        """
        timestamp = str(time.time())

        if screen_state and screen_state.get("path"):
            # Use existing screenshot path from screen_state
            return ShadowSnapshot(
                timestamp=timestamp,
                screenshot_path=screen_state["path"],
                metadata={"source": "screen_state"},
            )

        # Try to capture a fresh screenshot
        if self._capture and self._get_path:
            path = self._get_path()
            self._capture(path)
            return ShadowSnapshot(
                timestamp=timestamp,
                screenshot_path=path,
                metadata={"source": "fresh_capture"},
            )

        return None

    def snapshot_after(
        self, screen_state: Optional[Dict[str, Any]]
    ) -> Optional[ShadowSnapshot]:
        """Take a snapshot after the action.

        Always captures a fresh screenshot (does not reuse screen_state).
        Raises exceptions from capture_fn — caller (wrap) handles them.

        Args:
            screen_state: Current screen state (unused for after snapshot;
                         always captures fresh).

        Returns:
            ShadowSnapshot, or None if no capture function available.
        """
        timestamp = str(time.time())

        if self._capture and self._get_path:
            path = self._get_path()
            self._capture(path)
            return ShadowSnapshot(
                timestamp=timestamp,
                screenshot_path=path,
                metadata={"source": "fresh_capture"},
            )

        return None

    def compare(
        self,
        before: Optional[ShadowSnapshot],
        after: Optional[ShadowSnapshot],
    ) -> ShadowResult:
        """Compare before and after snapshots.

        Args:
            before: Before snapshot (may be None).
            after: After snapshot (may be None).

        Returns:
            ShadowResult with comparison outcome.
        """
        if before is None and after is None:
            return ShadowResult(
                before_snapshot=None,
                after_snapshot=None,
                changed=None,
                diff_summary="No snapshots available for comparison",
            )

        if before is None:
            return ShadowResult(
                before_snapshot=None,
                after_snapshot=after,
                changed=None,
                diff_summary="No before snapshot available for comparison",
            )

        if after is None:
            return ShadowResult(
                before_snapshot=before,
                after_snapshot=None,
                changed=None,
                diff_summary="No after snapshot available for comparison",
            )

        # Both snapshots present: byte-level comparison
        try:
            with open(before.screenshot_path, "rb") as fb:
                before_data = fb.read()
            with open(after.screenshot_path, "rb") as fa:
                after_data = fa.read()

            if before_data == after_data:
                return ShadowResult(
                    before_snapshot=before,
                    after_snapshot=after,
                    changed=False,
                    diff_summary="No visual change detected (identical files)",
                )
            else:
                return ShadowResult(
                    before_snapshot=before,
                    after_snapshot=after,
                    changed=True,
                    diff_summary="Screen changed: files differ",
                )
        except Exception as exc:
            return ShadowResult(
                before_snapshot=before,
                after_snapshot=after,
                changed=None,
                diff_summary=f"Comparison failed: {exc}",
                error=str(exc),
            )

    def wrap(
        self,
        action_callable: Callable[[], Dict[str, Any]],
        action: str,
        params: Dict[str, Any],
        screen_state: Optional[Dict[str, Any]] = None,
    ) -> tuple:
        """Wrap an action with before/after snapshot capture.

        Executes: before snapshot → action_callable() → after snapshot → compare.

        Args:
            action_callable: Zero-argument callable that executes the action
                            and returns the action result dict.
            action: Action name (for metadata).
            params: Action parameters (for metadata).
            screen_state: Current screen state for before snapshot.

        Returns:
            Tuple of (action_result: dict, shadow_result: ShadowResult).
            The action_result is exactly what action_callable() returned.
            Screenshot errors are captured in shadow_result.error and do NOT
            affect action_result.
        """
        error: Optional[str] = None

        # Before snapshot
        try:
            before = self.snapshot_before(screen_state)
        except Exception as exc:
            before = None
            error = f"Before snapshot failed: {exc}"

        # Execute the action (ALWAYS, even if before snapshot failed)
        action_result = action_callable()

        # After snapshot
        try:
            after = self.snapshot_after(screen_state)
        except Exception as exc:
            after = None
            if error:
                error += f"; After snapshot failed: {exc}"
            else:
                error = f"After snapshot failed: {exc}"

        # Compare
        compare_result = self.compare(before, after)

        # Merge any snapshot errors into the comparison result
        if error and compare_result.error:
            compare_result.error = f"{compare_result.error}; {error}"
        elif error:
            compare_result.error = error

        if before is not None and after is not None:
            capture_status = "captured"
        elif error:
            capture_status = "degraded"
        else:
            capture_status = "unavailable"
        compare_result.metadata = {"capture_status": capture_status}
        if error:
            compare_result.metadata["warnings"] = ["shadow_screenshot_capture_failed"]

        return action_result, compare_result
