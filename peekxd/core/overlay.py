"""Softbox Ghost Live Overlay for peekxd Linux (V3).

Provides a user-facing overlay for GHOST actions, allowing the user to
see a preview and explicitly approve or cancel before any action proceeds.

Key design rules:
- Overlay NEVER clicks or types. It is purely a confirmation surface.
- GHOST remains non-executing even if the user approves.
- Lazy imports: tkinter is imported only inside TkinterOverlayBackend.show().
- Headless/CI uses NoopOverlayBackend to avoid hangs.
"""

import logging
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class OverlayDecision:
    """Result of showing an overlay to the user."""

    approved: bool = False
    cancelled: bool = False
    timed_out: bool = False
    backend: str = "noop"
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "approved": self.approved,
            "cancelled": self.cancelled,
            "timed_out": self.timed_out,
            "backend": self.backend,
            "reason": self.reason,
        }


@dataclass
class OverlayRequest:
    """Request to show a ghost preview overlay."""

    action: str
    params: Dict[str, Any] = field(default_factory=dict)
    preview: Dict[str, Any] = field(default_factory=dict)
    screenshot_path: Optional[str] = None
    markup_path: Optional[str] = None
    timeout_seconds: int = 5

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action,
            "params": self.params,
            "preview": self.preview,
            "screenshot_path": self.screenshot_path,
            "markup_path": self.markup_path,
            "timeout_seconds": self.timeout_seconds,
        }


class BaseOverlayBackend:
    """Abstract base for overlay backends."""

    def show(self, request: OverlayRequest) -> OverlayDecision:
        """Show the overlay and return the user's decision.

        Must NOT perform any desktop actions.
        Must return within request.timeout_seconds in headless/CI.
        """
        raise NotImplementedError


class NoopOverlayBackend(BaseOverlayBackend):
    """Fallback backend that returns a controlled timed_out decision.

    Used when no GUI is available or in headless/CI environments.
    """

    def show(self, request: OverlayRequest) -> OverlayDecision:
        return OverlayDecision(
            approved=False,
            cancelled=False,
            timed_out=True,
            backend="noop",
            reason="No GUI backend available; automatic timeout",
        )


class TkinterOverlayBackend(BaseOverlayBackend):
    """Tkinter-based overlay that shows a preview window with Approve/Cancel.

    Lazy-imports tkinter only when show() is called.
    Never performs desktop actions.
    """

    def show(self, request: OverlayRequest) -> OverlayDecision:
        try:
            import tkinter as tk
            from tkinter import ttk
        except ImportError:
            logger.warning("tkinter not available, falling back to noop")
            return NoopOverlayBackend().show(request)

        decision = OverlayDecision(backend="tkinter")
        timeout_event = threading.Event()

        def _on_approve():
            decision.approved = True
            decision.reason = "User approved"
            timeout_event.set()
            root.destroy()

        def _on_cancel():
            decision.cancelled = True
            decision.reason = "User cancelled"
            timeout_event.set()
            root.destroy()

        def _on_timeout():
            if not timeout_event.is_set():
                decision.timed_out = True
                decision.reason = f"Timed out after {request.timeout_seconds}s"
                timeout_event.set()
                try:
                    root.destroy()
                except Exception:
                    pass

        try:
            root = tk.Tk()
            root.title("peekxd GHOST Preview")
            root.geometry("520x420")
            root.resizable(True, True)
            root.protocol("WM_DELETE_WINDOW", _on_cancel)

            # Schedule timeout
            root.after(request.timeout_seconds * 1000, _on_timeout)

            # Header
            header = ttk.Label(
                root,
                text=f"GHOST Action: {request.action}",
                font=("Helvetica", 14, "bold"),
                foreground="red",
            )
            header.pack(pady=(10, 5))

            # Risk factors
            preview = request.preview
            risk_factors = preview.get("risk_factors", [])
            reason = preview.get("reason", "")
            if risk_factors:
                risk_text = "Risk factors:\n" + "\n".join(f"  - {rf}" for rf in risk_factors)
                risk_label = ttk.Label(root, text=risk_text, foreground="orange")
                risk_label.pack(padx=10, pady=(0, 5), anchor="w")

            if reason:
                reason_label = ttk.Label(root, text=f"Reason: {reason}", wraplength=480)
                reason_label.pack(padx=10, pady=(0, 5), anchor="w")

            # Parameters (masked)
            params_display = preview.get("params", request.params)
            if params_display:
                param_text = "Parameters:\n" + "\n".join(
                    f"  {k}: {v}" for k, v in params_display.items()
                )
                param_label = ttk.Label(root, text=param_text, wraplength=480)
                param_label.pack(padx=10, pady=(0, 5), anchor="w")

            # Screenshot / markup image
            image_path = request.markup_path or request.screenshot_path
            image_label = None
            if image_path:
                try:
                    from PIL import Image, ImageTk

                    img = Image.open(image_path)
                    # Scale to fit
                    max_w, max_h = 480, 200
                    img.thumbnail((max_w, max_h))
                    photo = ImageTk.PhotoImage(img)
                    image_label = ttk.Label(root, image=photo)
                    image_label.image = photo  # prevent GC
                    image_label.pack(pady=5)
                except Exception as e:
                    logger.debug(f"Could not load preview image: {e}")
                    img_note = ttk.Label(root, text=f"(Preview image not available: {e})")
                    img_note.pack(pady=5)

            # Timeout info
            timeout_label = ttk.Label(
                root,
                text=f"Auto-cancel in {request.timeout_seconds}s",
                foreground="gray",
            )
            timeout_label.pack(pady=(5, 5))

            # Buttons
            btn_frame = ttk.Frame(root)
            btn_frame.pack(pady=10, fill="x", padx=20)

            approve_btn = ttk.Button(btn_frame, text="Approve", command=_on_approve)
            approve_btn.pack(side="left", expand=True, fill="x", padx=(0, 5))

            cancel_btn = ttk.Button(btn_frame, text="Cancel", command=_on_cancel)
            cancel_btn.pack(side="right", expand=True, fill="x", padx=(5, 0))

            root.mainloop()

        except Exception as e:
            logger.warning(f"Tkinter overlay failed: {e}")
            return OverlayDecision(
                approved=False,
                cancelled=False,
                timed_out=True,
                backend="tkinter",
                reason=f"Overlay error: {e}",
            )

        return decision


class GhostOverlayController:
    """Selects backend and shows ghost preview overlays.

    Auto-detects available GUI backends.
    Falls back to NoopOverlayBackend in headless environments.
    """

    def __init__(
        self,
        backend_name: Optional[str] = None,
        timeout: int = 5,
    ):
        self.timeout = timeout
        self._backend_name = backend_name
        self._backend: Optional[BaseOverlayBackend] = None

    @property
    def backend(self) -> BaseOverlayBackend:
        if self._backend is None:
            self._backend = self._create_backend()
        return self._backend

    def _create_backend(self) -> BaseOverlayBackend:
        name = (self._backend_name or "auto").lower()

        if name == "noop":
            return NoopOverlayBackend()

        if name == "tkinter":
            # Check if tkinter is available without importing it at module level
            try:
                import tkinter as _tk  # noqa: F401
                return TkinterOverlayBackend()
            except ImportError:
                logger.warning("tkinter requested but not available, using noop")
                return NoopOverlayBackend()

        if name == "auto":
            # Auto-detect: try tkinter first
            try:
                import tkinter as _tk  # noqa: F401
                return TkinterOverlayBackend()
            except ImportError:
                pass
            logger.info("No GUI backend detected, using noop overlay")
            return NoopOverlayBackend()

        # Unknown backend name
        logger.warning(f"Unknown overlay backend '{name}', using noop")
        return NoopOverlayBackend()

    def show_preview(self, request: OverlayRequest) -> OverlayDecision:
        """Show the overlay and return the user's decision.

        The overlay NEVER executes any action.
        """
        if request.timeout_seconds <= 0:
            request.timeout_seconds = self.timeout

        logger.info(f"Showing ghost overlay for action: {request.action}")
        decision = self.backend.show(request)
        logger.info(f"Overlay decision: {decision.to_dict()}")
        return decision
