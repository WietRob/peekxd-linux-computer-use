"""Safety middleware for peekxd MCP tools."""

from __future__ import annotations

import functools
from typing import Any, Callable, Dict, Optional

from ..core.audit import AuditLogger, get_logger
from ..core.overlay import GhostOverlayController, OverlayRequest
from ..core.safety import SafetyGuard, SafetyLevel
from ..core.shadow import ShadowRecorder
from ..core.zones import (
    GhostActionClassification,
    RiskDecision,
    Zone,
    ZoneDecision,
)


class SafetyMiddleware:
    """Apply SafetyGuard zone checks and audit logging to MCP tool calls."""

    def __init__(
        self,
        safety_guard: Optional[SafetyGuard] = None,
        audit_logger: Optional[AuditLogger] = None,
        shadow_recorder: Optional[ShadowRecorder] = None,
        capture_fn: Optional[Callable[[str], None]] = None,
        get_screenshot_path_fn: Optional[Callable[[], str]] = None,
        ghost_overlay: Optional[GhostOverlayController] = None,
    ) -> None:
        self.safety_guard = safety_guard or SafetyGuard(SafetyLevel.NORMAL)
        self.audit_logger = audit_logger or get_logger()
        self.shadow_recorder = shadow_recorder or ShadowRecorder(
            capture_fn=capture_fn,
            get_screenshot_path_fn=get_screenshot_path_fn,
        )
        self.ghost_overlay = ghost_overlay

    def wrap_tool(
        self,
        tool_name: str,
        func: Callable[..., Any],
    ) -> Callable[..., Dict[str, Any]]:
        """Wrap a tool function with safety classification and audit metadata."""

        @functools.wraps(func)
        def wrapped(*args: Any, **kwargs: Any) -> Dict[str, Any]:
            params = self._params_from_call(args, kwargs)
            decision = self.safety_guard.check_zone(tool_name, params)

            if decision.zone == Zone.GHOST:
                classification = ZoneDecision.classify_ghost_action(
                    tool_name, params, decision.risk_factors
                )

                # HARD_BLOCKED_GHOST: no overlay, immediate block
                if (
                    classification.classification
                    == GhostActionClassification.HARD_BLOCKED_GHOST
                ):
                    return self._blocked_response(tool_name, params, decision)

                # APPROVABLE_GHOST without overlay controller: backward compat block
                if self.ghost_overlay is None:
                    return self._blocked_response(tool_name, params, decision)

                # APPROVABLE_GHOST with overlay: show preview to user
                preview = ZoneDecision.create_ghost_preview(
                    tool_name, params, decision
                )
                overlay_request = OverlayRequest(
                    action=tool_name,
                    params=params,
                    preview=preview.to_dict(),
                )
                overlay_decision = self.ghost_overlay.show_preview(overlay_request)

                if not overlay_decision.approved:
                    # User denied or timed out — block with classification info
                    return self._blocked_response(
                        tool_name,
                        params,
                        decision,
                        classification=classification.classification,
                    )

                # Approved — proceed to execution with approval_source in audit

            try:
                if decision.zone == Zone.SHADOW:
                    raw_result, shadow_result = self.shadow_recorder.wrap(
                        action_callable=lambda: func(*args, **kwargs),
                        action=tool_name,
                        params=params,
                        screen_state=None,
                    )
                else:
                    raw_result = func(*args, **kwargs)
                    shadow_result = None
            except Exception as exc:
                self.audit_logger.log_action(
                    tool_name,
                    params,
                    result=decision.to_dict(),
                    error=str(exc),
                    zone=decision.zone.value,
                    executed=False,
                )
                raise

            result = self._envelope_result(raw_result)
            if shadow_result is not None:
                result["shadow"] = shadow_result.to_dict()
            # When a GHOST action was approved via overlay, record the approval source
            audit_result = result.copy()
            if decision.zone == Zone.GHOST:
                audit_result["approval_source"] = "overlay"
            entry = self.audit_logger.log_action(
                tool_name,
                params,
                result=audit_result,
                zone=decision.zone.value,
                executed=True,
            )
            result.update(self._metadata(decision, entry))
            return result

        return wrapped

    def _blocked_response(
        self,
        tool_name: str,
        params: Dict[str, Any],
        decision: RiskDecision,
        classification: Optional[GhostActionClassification] = None,
    ) -> Dict[str, Any]:
        error = f"Blocked by SafetyGuard: {decision.reason or 'GHOST zone action'}"
        result: Dict[str, Any] = {
            "success": False,
            "blocked": True,
            "error": error,
            "risk_factors": decision.risk_factors,
        }
        if decision.zone == Zone.GHOST:
            result["ghost_preview"] = ZoneDecision.create_ghost_preview(
                tool_name,
                params,
                decision,
            ).to_dict()
        if classification is not None:
            result["classification"] = classification.value
        entry = self.audit_logger.log_action(
            tool_name,
            params,
            result=result.copy(),
            error=error,
            zone=decision.zone.value,
            executed=False,
        )
        result.update(self._metadata(decision, entry))
        return result

    @staticmethod
    def _params_from_call(
        args: tuple[Any, ...],
        kwargs: Dict[str, Any],
    ) -> Dict[str, Any]:
        params = dict(kwargs)
        if args:
            params["args"] = list(args)
        return params

    @staticmethod
    def _envelope_result(raw_result: Any) -> Dict[str, Any]:
        if isinstance(raw_result, dict):
            return dict(raw_result)
        return {"result": raw_result}

    @staticmethod
    def _metadata(decision: RiskDecision, entry: Any) -> Dict[str, Any]:
        return {
            "zone": decision.zone.value,
            "risk_level": decision.risk_level,
            "risk_factors": decision.risk_factors,
            "audit_id": f"{entry.session_id}:{entry.step}",
        }


def install_global_safety_interceptor(mcp: Any, middleware: SafetyMiddleware) -> Any:
    """Route every subsequent FastMCP tool registration through SafetyMiddleware.

    FastMCP exposes registration as ``mcp.tool()`` decorators. Installing the
    interceptor once at server bootstrap keeps safety enforcement at that
    registration boundary, so later tools added to the same server cannot skip
    SafetyGuard by forgetting to use a local wrapper helper.
    """
    if vars(mcp).get("_peekxd_global_safety_interceptor_installed", False):
        return mcp

    original_tool = mcp.tool

    def intercepted_tool(*tool_args: Any, **tool_kwargs: Any) -> Callable[..., Any]:
        if len(tool_args) == 1 and callable(tool_args[0]) and not tool_kwargs:
            func = tool_args[0]
            return original_tool()(middleware.wrap_tool(func.__name__, func))

        original_decorator = original_tool(*tool_args, **tool_kwargs)

        def register(func: Callable[..., Any]) -> Any:
            return original_decorator(middleware.wrap_tool(func.__name__, func))

        return register

    setattr(mcp, "_peekxd_original_tool", original_tool)
    setattr(mcp, "tool", intercepted_tool)
    setattr(mcp, "_peekxd_global_safety_interceptor_installed", True)
    return mcp
