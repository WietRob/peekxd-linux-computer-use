"""Action sequences, wait conditions, and screen diffing for peekxd Linux.

Provides high-level automation primitives:
- ActionSequence: Chain multiple actions (click, type, key, wait) together
- WaitCondition: Wait for an element to appear/disappear or screen to change
- ScreenDiff: Compare screenshots to detect changes
"""

import hashlib
import os
import tempfile
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from ..core.errors import peekxdError, VisionError


@dataclass
class ActionStep:
    """A single step in an action sequence."""

    action: str  # "click", "type", "key", "hotkey", "move", "scroll", "wait", "capture", "find_click"
    params: Dict[str, Any] = field(default_factory=dict)
    description: str = ""
    retry: int = 1  # Number of retries on failure
    delay_after: float = 0.5  # Seconds to wait after this step


class ActionSequence:
    """Execute a sequence of actions with error handling and retries.

    Example:
        seq = ActionSequence()
        seq.click(100, 200, description="Click login button")
        seq.wait(1.0)
        seq.type("username", description="Enter username")
        seq.key("Tab")
        seq.type("password")
        seq.key("Return")
        results = seq.execute()
    """

    def __init__(self, screenshot_provider=None, input_provider=None, vision_provider=None):
        self.steps: List[ActionStep] = []
        self.results: List[Dict[str, Any]] = []
        self._screenshot = screenshot_provider
        self._input = input_provider
        self._vision = vision_provider

    # --- Builder methods ---

    def click(self, x: int, y: int, button: str = "left", description: str = "", delay_after: float = 0.5) -> "ActionSequence":
        """Add a click action."""
        self.steps.append(ActionStep(
            action="click",
            params={"x": x, "y": y, "button": button},
            description=description or f"Click {button} at ({x},{y})",
            delay_after=delay_after,
        ))
        return self

    def find_click(self, description: str, button: str = "left", retry: int = 3, delay_after: float = 0.5) -> "ActionSequence":
        """Add a find-and-click action using vision."""
        self.steps.append(ActionStep(
            action="find_click",
            params={"description": description, "button": button},
            description=f"Find and click: {description}",
            retry=retry,
            delay_after=delay_after,
        ))
        return self

    def type(self, text: str, description: str = "", delay_after: float = 0.3) -> "ActionSequence":
        """Add a type action."""
        self.steps.append(ActionStep(
            action="type",
            params={"text": text},
            description=description or f"Type: {text[:30]}",
            delay_after=delay_after,
        ))
        return self

    def key(self, key_name: str, description: str = "", delay_after: float = 0.3) -> "ActionSequence":
        """Add a key press action."""
        self.steps.append(ActionStep(
            action="key",
            params={"key": key_name},
            description=description or f"Press: {key_name}",
            delay_after=delay_after,
        ))
        return self

    def hotkey(self, *keys: str, description: str = "", delay_after: float = 0.3) -> "ActionSequence":
        """Add a hotkey action."""
        self.steps.append(ActionStep(
            action="hotkey",
            params={"keys": list(keys)},
            description=description or f"Hotkey: {'+'.join(keys)}",
            delay_after=delay_after,
        ))
        return self

    def move(self, x: int, y: int, description: str = "", delay_after: float = 0.3) -> "ActionSequence":
        """Add a mouse move action."""
        self.steps.append(ActionStep(
            action="move",
            params={"x": x, "y": y},
            description=description or f"Move to ({x},{y})",
            delay_after=delay_after,
        ))
        return self

    def scroll(self, direction: str = "down", amount: int = 3, description: str = "", delay_after: float = 0.3) -> "ActionSequence":
        """Add a scroll action."""
        self.steps.append(ActionStep(
            action="scroll",
            params={"direction": direction, "amount": amount},
            description=description or f"Scroll {direction} x{amount}",
            delay_after=delay_after,
        ))
        return self

    def wait(self, seconds: float = 1.0, description: str = "") -> "ActionSequence":
        """Add a wait action."""
        self.steps.append(ActionStep(
            action="wait",
            params={"seconds": seconds},
            description=description or f"Wait {seconds}s",
            delay_after=0,
        ))
        return self

    def capture(self, description: str = "", delay_after: float = 0.3) -> "ActionSequence":
        """Add a screen capture action."""
        self.steps.append(ActionStep(
            action="capture",
            params={},
            description=description or "Capture screen",
            delay_after=delay_after,
        ))
        return self

    def wait_for_change(self, timeout: float = 10.0, description: str = "", delay_after: float = 0.3) -> "ActionSequence":
        """Add a wait-for-screen-change action."""
        self.steps.append(ActionStep(
            action="wait_for_change",
            params={"timeout": timeout},
            description=description or f"Wait for change ({timeout}s)",
            delay_after=delay_after,
        ))
        return self

    def wait_for_element(self, description: str, timeout: float = 10.0, delay_after: float = 0.3) -> "ActionSequence":
        """Add a wait-for-element action using vision."""
        self.steps.append(ActionStep(
            action="wait_for_element",
            params={"description": description, "timeout": timeout},
            description=f"Wait for element: {description}",
            delay_after=delay_after,
        ))
        return self

    def execute(self, stop_on_error: bool = True,
                safety_gate=None) -> List[Dict[str, Any]]:
        """Execute all steps in the sequence.

        Every step passes through the canonical SafetyDecisionGate
        (G3): SHADOW/DIRECT execute with evidence correlation; APPROVABLE_GHOST
        requires a prior per-decision approval consumed exactly once;
        HARD_BLOCKED_GHOST and denials/timeout/replay execute nothing.
        ``peekxd macro run`` and every other ActionSequence consumer is
        covered by this single boundary.
        """
        from ..input import get_input_provider
        from ..core.decision import (
            DecisionDeniedError,
            get_gate,
        )

        if self._input is None:
            self._input = get_input_provider()

        gate = safety_gate or get_gate()
        self.results = []

        for i, step in enumerate(self.steps):
            result = {"step": i, "action": step.action, "description": step.description, "success": False}

            # ---- canonical SafetyDecision boundary (no execution without it)
            try:
                decision = gate.evaluate(
                    step.action, step.params, entry_point="macro",
                )
                result["safety_decision_id"] = decision.decision_id
                result["safety_policy"] = decision.policy_result
                result["evidence_correlation_id"] = decision.evidence_correlation_id

                if decision.policy_result == "require_approval":
                    # Redeem a prior out-of-band approval bound to the exact
                    # action + payload (params digest). None → stays pending.
                    prior = gate.store.find_approved_unconsumed(
                        decision.action, decision.params_digest)
                    if prior is not None and gate.store.consume(prior["decision_id"]):
                        result["redeemed_approval_decision_id"] = prior["decision_id"]
                        # approval redeemed → fall through to execution below
                    else:
                        result.update({
                            "success": False,
                            "blocked": True,
                            "error": (
                                f"APPROVABLE_GHOST pending approval "
                                f"(decision {decision.decision_id}, "
                                f"expires {decision.expiry})"
                            ),
                            "pending_approval": True,
                            "decision": decision.to_dict(),
                        })
                        self.results.append(result)
                        if stop_on_error:
                            break
                        continue

                if decision.policy_result == "require_approval":
                    # reached only when a prior approval was redeemed above
                    pass
                elif not gate.is_execution_allowed(decision):
                    raise DecisionDeniedError(decision)
                elif not gate.consume(decision):
                    raise DecisionDeniedError(decision)

            except DecisionDeniedError as exc:
                result.update({
                    "success": False,
                    "blocked": True,
                    "error": str(exc),
                    "decision": exc.decision.to_dict(),
                })
                self.results.append(result)
                if stop_on_error:
                    break
                continue
            # ---- boundary end

            for attempt in range(step.retry):
                try:
                    self._execute_step(step, result)
                    result["success"] = True
                    result["attempts"] = attempt + 1
                    break
                except Exception as exc:
                    result["error"] = str(exc)
                    result["attempts"] = attempt + 1
                    if attempt < step.retry - 1:
                        time.sleep(0.5 * (attempt + 1))

            self.results.append(result)

            if step.delay_after > 0:
                time.sleep(step.delay_after)

            if not result["success"] and stop_on_error:
                break

        return self.results

    def _execute_step(self, step: ActionStep, result: Dict[str, Any]):
        """Execute a single step."""
        p = step.params

        if step.action == "click":
            self._input.click(p["x"], p["y"], p.get("button", "left"))
            result["detail"] = f"clicked at ({p['x']},{p['y']})"

        elif step.action == "find_click":
            raise peekxdError("Screenshot/vision find_click was removed; use semantic element IDs from `peekxd see --semantic`.")

        elif step.action == "type":
            self._input.type_text(p["text"])
            result["detail"] = f"typed {len(p['text'])} chars"

        elif step.action == "key":
            self._input.key_press(p["key"])
            result["detail"] = f"pressed {p['key']}"

        elif step.action == "hotkey":
            self._input.hotkey(*p["keys"])
            result["detail"] = f"hotkey {'+'.join(p['keys'])}"

        elif step.action == "move":
            self._input.move_mouse(p["x"], p["y"])
            result["detail"] = f"moved to ({p['x']},{p['y']})"

        elif step.action == "scroll":
            self._input.scroll(p["direction"], p["amount"])
            result["detail"] = f"scrolled {p['direction']} x{p['amount']}"

        elif step.action == "wait":
            time.sleep(p["seconds"])
            result["detail"] = f"waited {p['seconds']}s"

        elif step.action == "capture":
            result["detail"] = "capture skipped (screenshot removed)"

        elif step.action == "wait_for_change":
            result["detail"] = "wait_for_change skipped (screenshot removed)"

        elif step.action == "wait_for_element":
            result["detail"] = "wait_for_element skipped (vision removed)"

        else:
            raise peekxdError(f"Unknown action: {step.action}")

    def to_dict(self) -> List[Dict[str, Any]]:
        """Serialize the sequence to a list of dicts."""
        return [
            {
                "action": s.action,
                "params": s.params,
                "description": s.description,
                "retry": s.retry,
                "delay_after": s.delay_after,
            }
            for s in self.steps
        ]

    @classmethod
    def from_dict(cls, data: List[Dict[str, Any]]) -> "ActionSequence":
        """Deserialize from a list of dicts."""
        seq = cls()
        for item in data:
            seq.steps.append(ActionStep(
                action=item["action"],
                params=item["params"],
                description=item.get("description", ""),
                retry=item.get("retry", 1),
                delay_after=item.get("delay_after", 0.5),
            ))
        return seq


class ScreenDiff:
    """Compare screenshots to detect changes."""

    def __init__(self):
        self.last_screenshot: Optional[str] = None
        self.last_hash: Optional[str] = None

    def capture_and_hash(self, output_path: Optional[str] = None) -> Tuple[str, str]:
        """Screenshot diffing was removed with pixel capture."""
        del output_path
        raise peekxdError("ScreenDiff was removed because it requires screenshot capture; use semantic state polling instead.")

    def has_changed(self, threshold: float = 0.1) -> bool:
        """Check if the screen has changed since last capture.

        Args:
            threshold: Minimum fraction of pixels that must differ (0.0-1.0).

        Returns:
            True if screen has changed significantly.
        """
        if self.last_hash is None:
            self.capture_and_hash()
            return True  # First call always "changed"

        old_hash = self.last_hash
        _, new_hash = self.capture_and_hash()

        # Simple hamming distance on perceptual hash
        try:
            diff_bits = bin(int(old_hash, 16) ^ int(new_hash, 16)).count("1")
            max_bits = len(old_hash) * 4
            ratio = diff_bits / max_bits
            return ratio > threshold
        except (ValueError, ZeroDivisionError):
            return old_hash != new_hash

    def wait_for_change(
        self,
        timeout: float = 10.0,
        poll_interval: float = 1.0,
        threshold: float = 0.1,
    ) -> Dict[str, Any]:
        """Wait until the screen changes.

        Args:
            timeout: Maximum seconds to wait.
            poll_interval: Seconds between checks.
            threshold: Change detection threshold.

        Returns:
            Dict with 'changed', 'elapsed', and 'screenshot_path'.
        """
        start = time.time()
        self.capture_and_hash()  # Baseline

        while time.time() - start < timeout:
            time.sleep(poll_interval)
            if self.has_changed(threshold):
                elapsed = time.time() - start
                return {
                    "changed": True,
                    "elapsed": round(elapsed, 2),
                    "screenshot_path": self.last_screenshot,
                }

        return {
            "changed": False,
            "elapsed": round(time.time() - start, 2),
            "screenshot_path": self.last_screenshot,
        }

    def wait_for_stable(
        self,
        timeout: float = 10.0,
        poll_interval: float = 0.5,
        stable_duration: float = 1.5,
    ) -> Dict[str, Any]:
        """Wait until the screen stops changing (stable).

        Args:
            timeout: Maximum seconds to wait.
            poll_interval: Seconds between checks.
            stable_duration: Seconds of no change to consider stable.

        Returns:
            Dict with 'stable', 'elapsed', and 'screenshot_path'.
        """
        start = time.time()
        last_change_time = start
        self.capture_and_hash()  # Baseline

        while time.time() - start < timeout:
            time.sleep(poll_interval)
            if self.has_changed():
                last_change_time = time.time()
            elif time.time() - last_change_time >= stable_duration:
                elapsed = time.time() - start
                return {
                    "stable": True,
                    "elapsed": round(elapsed, 2),
                    "screenshot_path": self.last_screenshot,
                }

        return {
            "stable": False,
            "elapsed": round(time.time() - start, 2),
            "screenshot_path": self.last_screenshot,
        }


class WaitCondition:
    """Wait for specific conditions on screen."""

    @staticmethod
    def _snapshot_metadata(snapshot: Dict[str, Any]) -> Dict[str, Any]:
        """Return deterministic metadata for the last observed semantic snapshot."""
        payload = dict(snapshot.get("snapshot") or {})
        return {
            "snapshot_id": payload.get("snapshot_id"),
            "created_at": payload.get("created_at"),
            "ttl_seconds": payload.get("ttl_seconds"),
            "cache_ttl_remaining_seconds": payload.get("cache_ttl_remaining_seconds"),
            "cached": payload.get("cached"),
            "source": dict(payload.get("source") or {}),
            "meta": dict(snapshot.get("meta") or {}),
            "result": dict(snapshot.get("result") or {}),
        }

    @staticmethod
    def _matching_element(
        snapshot: Dict[str, Any],
        query: str,
        *,
        text_only: bool = False,
    ) -> Optional[Dict[str, Any]]:
        query_l = str(query).casefold()
        for element in snapshot.get("snapshot", {}).get("elements", []) or []:
            fields = [element.get("name"), element.get("label")]
            if not text_only:
                fields.extend(
                    [
                        element.get("element_id"),
                        element.get("raw_element_id"),
                        element.get("role"),
                        element.get("path"),
                    ]
                )
            if any(query_l in str(field or "").casefold() for field in fields):
                return dict(element)
        return None

    @staticmethod
    def for_semantic_query(
        query: str,
        timeout: float = 10.0,
        poll_interval: float = 0.5,
        *,
        text_only: bool = False,
        snapshot_builder: Any = None,
        sleeper: Any = time.sleep,
        monotonic: Any = time.monotonic,
        **snapshot_kwargs: Any,
    ) -> Dict[str, Any]:
        """Poll semantic snapshots until an element or text query is observed."""
        if snapshot_builder is None:
            from ..semantic import build_semantic_snapshot

            snapshot_builder = build_semantic_snapshot
        if timeout < 0:
            raise ValueError("timeout must be greater than or equal to zero")
        if poll_interval < 0:
            raise ValueError("poll_interval must be greater than or equal to zero")

        started = monotonic()
        deadline = started + float(timeout)
        snapshots_observed = 0
        last_snapshot: Optional[Dict[str, Any]] = None

        while True:
            snapshot = snapshot_builder(**snapshot_kwargs)
            snapshots_observed += 1
            last_snapshot = snapshot
            matched = WaitCondition._matching_element(snapshot, query, text_only=text_only)
            if matched is not None:
                return {
                    "success": True,
                    "found": True,
                    "query": query,
                    "matched_element": matched,
                    "snapshots_observed": snapshots_observed,
                    "elapsed": round(monotonic() - started, 2),
                    "last_snapshot": WaitCondition._snapshot_metadata(snapshot),
                }

            if monotonic() >= deadline:
                return {
                    "success": False,
                    "found": False,
                    "query": query,
                    "matched_element": None,
                    "snapshots_observed": snapshots_observed,
                    "elapsed": round(monotonic() - started, 2),
                    "last_snapshot": WaitCondition._snapshot_metadata(last_snapshot or {}),
                    "error": f"timed out waiting for semantic query: {query}",
                }
            if poll_interval:
                sleeper(poll_interval)

    @staticmethod
    def for_semantic_element(
        description: str,
        timeout: float = 10.0,
        poll_interval: float = 0.5,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Wait for an accessible semantic element to appear."""
        return WaitCondition.for_semantic_query(
            description,
            timeout=timeout,
            poll_interval=poll_interval,
            text_only=False,
            **kwargs,
        )

    @staticmethod
    def for_semantic_text(
        text: str,
        timeout: float = 10.0,
        poll_interval: float = 0.5,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Wait for accessible text to appear in semantic element labels/names."""
        return WaitCondition.for_semantic_query(
            text,
            timeout=timeout,
            poll_interval=poll_interval,
            text_only=True,
            **kwargs,
        )

    @staticmethod
    def for_element(
        description: str,
        timeout: float = 10.0,
        poll_interval: float = 1.0,
        vision_provider=None,
        screenshot_provider=None,
    ) -> Dict[str, Any]:
        """Wait for an element described by text to appear on screen.

        Args:
            description: Text description of the element to wait for.
            timeout: Maximum seconds to wait.
            poll_interval: Seconds between checks.
            vision_provider: Optional vision provider.
            screenshot_provider: Optional screenshot provider.

        Returns:
            Dict with 'found', 'position', 'elapsed', 'screenshot_path'.
        """
        del description, timeout, poll_interval, vision_provider, screenshot_provider
        raise peekxdError("Vision/screenshot wait_for_element was removed; use AT-SPI semantic polling instead.")

    @staticmethod
    def for_text(
        text: str,
        timeout: float = 10.0,
        poll_interval: float = 1.0,
        vision_provider=None,
        screenshot_provider=None,
    ) -> Dict[str, Any]:
        """Wait for specific text to appear on screen.

        Uses vision analysis to check if the text is visible.
        """
        del text, timeout, poll_interval, vision_provider, screenshot_provider
        raise peekxdError("Vision/screenshot wait_for_text was removed; use AT-SPI semantic polling instead.")

    @staticmethod
    def for_no_change(
        timeout: float = 10.0,
        poll_interval: float = 0.5,
        threshold: float = 0.05,
    ) -> Dict[str, Any]:
        """Wait until the screen stops changing."""
        differ = ScreenDiff()
        return differ.wait_for_stable(timeout, poll_interval, stable_duration=1.0)
