"""Softbox zone system for peekxd Linux.

Provides risk-based zone assignment for actions:
- GHOST    — Preview only, no execution
- SHADOW   — Execute with before/after snapshot + audit (backlog for V1)
- GUIDED   — Normal guardrails + audit
- DIRECT   — Direct execution for trusted low-risk actions
"""

import enum
import fnmatch
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


class Zone(enum.Enum):
    """Softbox execution zones."""

    GHOST = "ghost"       # Preview only, no execution
    SHADOW = "shadow"     # Execute with full audit + snapshots (backlog)
    GUIDED = "guided"     # Normal guardrails + audit
    DIRECT = "direct"     # Direct execution, minimal checks


class GhostActionClassification(enum.Enum):
    """Classification of GHOST actions for approval execution (V4)."""
    HARD_BLOCKED_GHOST = "hard_blocked_ghost"   # Never executes, even with approval
    APPROVABLE_GHOST = "approvable_ghost"       # May execute after explicit approval


@dataclass
class GhostPreviewResult:
    """Structured preview for ghost-mode actions."""

    action: str
    params: Dict[str, Any]
    zone: Zone
    risk_factors: List[str] = field(default_factory=list)
    reason: str = ""
    requires_confirmation: bool = True
    target_coordinates: Optional[tuple] = None
    text_preview: Optional[str] = None
    markup_path: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action,
            "params": self._mask_sensitive_params(),
            "zone": self.zone.value,
            "risk_factors": self.risk_factors,
            "reason": self.reason,
            "requires_confirmation": self.requires_confirmation,
            "required_confirmation": self.requires_confirmation,
            "target_coordinates": self.target_coordinates,
            "text_preview": self.text_preview,
            "markup_path": self.markup_path,
        }

    def _mask_sensitive_params(self) -> Dict[str, Any]:
        """Mask potentially sensitive values in params."""
        masked = {}
        sensitive_keys = {"text", "password", "token", "secret", "key", "api_key"}
        for k, v in self.params.items():
            if k.lower() in sensitive_keys and isinstance(v, str) and len(v) > 0:
                masked[k] = "*" * min(len(v), 8)
            else:
                masked[k] = v
        return masked


@dataclass
class GhostApprovalDecision:
    """V4 decision on whether a GHOST action can be executed after approval."""
    classification: GhostActionClassification
    can_execute_after_approval: bool
    hard_block_reason: Optional[str] = None
    approval_required: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "classification": self.classification.value,
            "can_execute_after_approval": self.can_execute_after_approval,
            "hard_block_reason": self.hard_block_reason,
            "approval_required": self.approval_required,
        }


@dataclass
class RiskDecision:
    """Result of a risk assessment for an action."""

    zone: Zone
    risk_level: str  # "safe", "warn", "destructive", "unknown"
    risk_factors: List[str] = field(default_factory=list)
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone": self.zone.value,
            "risk_level": self.risk_level,
            "risk_factors": self.risk_factors,
            "reason": self.reason,
        }


class ZoneDecision:
    """Risk-based zone assignment for peekxd actions.

    Decides which Softbox zone an action should execute in based on
    action type, parameters, and heuristics.

    Example:
        decision = ZoneDecision.decide("click", {"x": 100, "y": 200})
        assert decision.zone == Zone.SHADOW  # V2: click → SHADOW

        decision = ZoneDecision.decide("type", {"text": "rm -rf /"})
        assert decision.zone == Zone.GHOST
    """

    # Actions that are read-only / observational and do not capture pixels.
    _READONLY_ACTIONS = {
        "list_windows",
        "find_element",
        "inspect_ui",
        "get_ui_tree",
        "get_active_window",
        "see_semantic",
        "peekxd_ghost_preview",
        "peekxd_audit_export",
        "peekxd_zone_check",
    }

    # Removed pixel-capture/vision actions. These must never be classified as
    # DIRECT just because they used to be observational.
    _REMOVED_SCREENSHOT_ACTIONS = {
        "capture_screen",
        "mark_elements",
        "screenshot",
        "analyze_screen",
        "analyze_image",
        "find_and_click",
        "type_into_field",
        "screen_has_changed",
    }

    # Actions that execute with before/after snapshot (Shadow Mode V2)
    _SHADOW_ACTIONS = {
        "click", "drag",
    }

    # Actions that modify state but are generally low-risk
    _LOW_RISK_ACTIONS = {
        "move_mouse", "scroll", "wait", "wait_for_element", "wait_for_text",
        "focus_window", "key", "press_key", "hotkey",
        "peekxd_set_safety_level",
    }

    # Actions that modify data
    _MODIFYING_ACTIONS = {
        "type", "type_text", "type_into_field",
    }

    # Destructive shell command patterns (checked in text params)
    _DESTRUCTIVE_PATTERNS = [
        "rm ", "sudo ", "dd ", "mkfs", "fdisk", "shred ", "wipe ",
        "format ", "*delete*", "*remove*", "*DROP*", "*TRUNCATE*",
    ]

    # Credential-like patterns
    _CREDENTIAL_PATTERNS = [
        "password", "passwd", "token", "secret", "api_key",
        "private_key", "ssh_key", "credentials",
    ]

    @classmethod
    def decide(cls, action: str, params: Dict[str, Any]) -> RiskDecision:
        """Decide which zone an action should execute in.

        Args:
            action: Action name (click, type, etc.)
            params: Action parameters.

        Returns:
            RiskDecision with zone assignment.
        """
        action = action.strip().lower()
        risk_factors: List[str] = []

        if action in cls._REMOVED_SCREENSHOT_ACTIONS:
            return RiskDecision(
                zone=Zone.GHOST,
                risk_level="blocked",
                risk_factors=[f"removed_screenshot_action: {action}"],
                reason=(
                    "Pixel/screenshot capture actions were removed; "
                    "use semantic state instead"
                ),
            )

        # 1. Check for destructive patterns in text (highest priority)
        text = params.get("text", "")
        if isinstance(text, str):
            for pattern in cls._DESTRUCTIVE_PATTERNS:
                if pattern.lower().strip("*") in text.lower() or fnmatch.fnmatch(
                    text.lower(), pattern.lower()
                ):
                    risk_factors.append(f"destructive_pattern: '{pattern}'")

        # 2. Check for credential-like text
        if isinstance(text, str):
            for pattern in cls._CREDENTIAL_PATTERNS:
                if pattern in text.lower():
                    risk_factors.append(f"credential_pattern: '{pattern}'")

        # 3. Check for system-level key combinations
        if action in ("key", "hotkey"):
            keys = params.get("hotkey", []) or [params.get("key", "")]
            keys_str = "+".join(str(k) for k in keys).lower()
            if "ctrl+alt+delete" in keys_str:
                risk_factors.append("system_key_combo: ctrl+alt+delete")
            if "ctrl+alt+t" in keys_str:
                risk_factors.append("system_key_combo: ctrl+alt+t")

        # 4. Check for protected paths in output_path
        output_path = params.get("output_path", "")
        if isinstance(output_path, str):
            protected = ["/", "/bin", "/sbin", "/usr/bin", "/usr/sbin",
                         "/etc", "/boot", "/dev", "/proc", "/sys",
                         "/lib", "/lib64", "/usr/lib", "/usr/lib64"]
            for p in protected:
                if output_path.startswith(p):
                    risk_factors.append(f"protected_path: {p}")

        # 5. Check for unknown actions
        known_actions = (
            cls._READONLY_ACTIONS
            | cls._SHADOW_ACTIONS
            | cls._LOW_RISK_ACTIONS
            | cls._MODIFYING_ACTIONS
            | cls._REMOVED_SCREENSHOT_ACTIONS
        )
        if action not in known_actions:
            risk_factors.append(f"unknown_action: {action}")

        # --- Zone assignment based on risk factors ---

        if risk_factors:
            # Any risk factor -> GHOST (conservative)
            return RiskDecision(
                zone=Zone.GHOST,
                risk_level=(
                    "destructive"
                    if any("destructive" in f for f in risk_factors)
                    else "warn"
                ),
                risk_factors=risk_factors,
                reason=f"Risk factors detected: {', '.join(risk_factors)}",
            )

        # 6. Read-only / observational actions -> DIRECT.
        if action in cls._READONLY_ACTIONS:
            return RiskDecision(
                zone=Zone.DIRECT,
                risk_level="safe",
                risk_factors=[],
                reason="Read-only observation action",
            )

        # Shadow actions (V2): execute with before/after snapshot
        if action in cls._SHADOW_ACTIONS:
            return RiskDecision(
                zone=Zone.SHADOW,
                risk_level="safe",
                risk_factors=[],
                reason="UI-modifying action, executing with shadow snapshot",
            )

        # Low-risk actions without risk factors -> DIRECT
        if action in cls._LOW_RISK_ACTIONS:
            return RiskDecision(
                zone=Zone.DIRECT,
                risk_level="safe",
                risk_factors=[],
                reason="Low-risk action with no risk factors",
            )

        # Modifying actions without risk factors -> SHADOW (Shadow Mode V2)
        if action in cls._MODIFYING_ACTIONS:
            return RiskDecision(
                zone=Zone.SHADOW,
                risk_level="safe",
                risk_factors=[],
                reason="Data-modifying action, executing with shadow snapshot",
            )

        # Unknown action without risk factors -> GUIDED (conservative)
        return RiskDecision(
            zone=Zone.GUIDED,
            risk_level="unknown",
            risk_factors=["unknown_action_type"],
            reason=f"Unknown action type '{action}', defaulting to GUIDED",
        )

    @classmethod
    def create_ghost_preview(
        cls,
        action: str,
        params: Dict[str, Any],
        decision: RiskDecision,
        screenshot_path: Optional[str] = None,
    ) -> GhostPreviewResult:
        """Create a ghost preview for an action.

        Args:
            action: Action name.
            params: Action parameters.
            decision: RiskDecision that assigned GHOST zone.
            screenshot_path: Optional path to current screenshot for visual preview.

        Returns:
            GhostPreviewResult with preview details.
        """
        preview = GhostPreviewResult(
            action=action,
            params=params,
            zone=Zone.GHOST,
            risk_factors=decision.risk_factors,
            reason=decision.reason,
            requires_confirmation=True,
        )

        # Extract target coordinates if present
        if "x" in params and "y" in params:
            preview.target_coordinates = (params["x"], params["y"])

        # Extract text preview if present
        text = params.get("text", "")
        if isinstance(text, str) and text:
            preview.text_preview = text[:50] + "..." if len(text) > 50 else text

        # Generate visual preview artifact if screenshot and coordinates available
        if screenshot_path and preview.target_coordinates:
            try:
                preview.markup_path = cls._generate_preview_markup(
                    screenshot_path, preview.target_coordinates, action
                )
            except Exception:
                # Visual preview is optional; don't fail if PIL missing or error
                pass

        return preview

    @classmethod
    def classify_ghost_action(
        cls,
        action: str,
        params: Dict[str, Any],
        risk_factors: List[str],
        force_ghost: bool = False,
    ) -> GhostApprovalDecision:
        """Classify a GHOST action as HARD_BLOCKED or APPROVABLE (V4).

        Safety rules:
        - force_ghost=True -> ALWAYS hard-blocked
        - Any risk factor at all -> hard-blocked
        - Unknown actions -> hard-blocked
        - Only known safe actions with ZERO risk factors -> approvable

        Args:
            action: Action name.
            params: Action parameters.
            risk_factors: Risk factors from zone decision.
            force_ghost: Whether force_ghost CLI flag is active.

        Returns:
            GhostApprovalDecision with classification.
        """
        # force_ghost always hard-blocks
        if force_ghost:
            return GhostApprovalDecision(
                classification=GhostActionClassification.HARD_BLOCKED_GHOST,
                can_execute_after_approval=False,
                hard_block_reason="force_ghost is active",
                approval_required=True,
            )

        # Any risk factors -> hard-blocked.
        if risk_factors:
            return GhostApprovalDecision(
                classification=GhostActionClassification.HARD_BLOCKED_GHOST,
                can_execute_after_approval=False,
                hard_block_reason=f"Risk factors present: {', '.join(risk_factors)}",
                approval_required=True,
            )

        # Unknown actions -> hard-blocked
        approvable_actions = (
            cls._SHADOW_ACTIONS | cls._LOW_RISK_ACTIONS | cls._MODIFYING_ACTIONS
        )
        if action.strip().lower() not in approvable_actions:
            return GhostApprovalDecision(
                classification=GhostActionClassification.HARD_BLOCKED_GHOST,
                can_execute_after_approval=False,
                hard_block_reason=f"Action '{action}' is not in approvable set",
                approval_required=True,
            )

        # Known safe action with zero risk factors -> approvable
        return GhostApprovalDecision(
            classification=GhostActionClassification.APPROVABLE_GHOST,
            can_execute_after_approval=True,
            hard_block_reason=None,
            approval_required=True,
        )

    @classmethod
    def _generate_preview_markup(
        cls,
        screenshot_path: str,
        coordinates: tuple,
        action: str,
        output_path: Optional[str] = None,
    ) -> str:
        """Generate a visual preview image with target marker.

        Draws a highlighted circle/box at the target coordinates on the screenshot
        to show where the action WOULD happen.

        Args:
            screenshot_path: Path to source screenshot.
            coordinates: (x, y) target coordinates.
            action: Action name for label.
            output_path: Where to save. If None, creates temp file.

        Returns:
            Path to generated preview image.
        """
        try:
            from PIL import Image, ImageDraw, ImageFont
        except ImportError:
            raise  # Let caller handle

        img = Image.open(screenshot_path)
        draw = ImageDraw.Draw(img)

        x, y = int(coordinates[0]), int(coordinates[1])

        # Draw target crosshair (red)
        crosshair_size = 20
        draw.line([x - crosshair_size, y, x + crosshair_size, y], fill="red", width=3)
        draw.line([x, y - crosshair_size, x, y + crosshair_size], fill="red", width=3)

        # Draw circle around target
        draw.ellipse([x - 25, y - 25, x + 25, y + 25], outline="red", width=3)

        # Label
        label = f"[GHOST] {action} would happen here"
        try:
            font = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                14,
            )
        except (OSError, IOError):
            font = ImageFont.load_default()

        # Text background
        bbox = draw.textbbox((0, 0), label, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw.rectangle([x + 30, y - th - 4, x + 30 + tw + 4, y + 4], fill="red")
        draw.text((x + 32, y - th - 2), label, fill="white", font=font)

        if output_path is None:
            import tempfile
            output_path = os.path.join(
                tempfile.gettempdir(),
                f"ghost_preview_{action}_{int(time.time())}.png",
            )

        img.save(output_path)
        return output_path
