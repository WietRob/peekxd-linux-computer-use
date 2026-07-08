"""Safety middleware for peekxd MCP tools."""

from __future__ import annotations

import functools
from typing import Any, Awaitable, Callable, Dict, List, Optional, Union, cast

from ..core.audit import AuditLogger, get_logger
from ..core.errors import InterceptorNotActiveError, PermissionDeniedError
from ..core.overlay import GhostOverlayController, OverlayRequest
from ..core.safety import SafetyGuard, SafetyLevel
from ..core.shadow import ShadowRecorder
from ..core.zones import (
    GhostActionClassification,
    RiskDecision,
    Zone,
    ZoneDecision,
)
from ..safety.overlay import build_ghost_overlay_context

MCP_SAFETY_CAPABILITY_VERSION = "peekxd.mcp_safety.v1"


def build_safety_capability(
    *,
    registration_interceptor: bool,
    dispatch_guard: bool,
) -> Dict[str, Any]:
    """Return the stable MCP safety capability advertised at initialize."""
    return {
        "name": "peekxd_safety",
        "version": MCP_SAFETY_CAPABILITY_VERSION,
        "registration_interceptor": registration_interceptor,
        "dispatch_guard": dispatch_guard,
        "audit_id": "required",
    }


class SafetyMiddleware:
    """Apply SafetyGuard zone checks and audit logging to MCP tool calls."""

    def __init__(
        self,
        safety_guard: Optional[SafetyGuard] = None,
        audit_logger: Optional[AuditLogger] = None,
        shadow_recorder: Optional[ShadowRecorder] = None,
        capture_fn: Optional[Callable[[str], None]] = None,
        get_screenshot_path_fn: Optional[Callable[[], str]] = None,
        ghost_overlay: Optional[
            Union[GhostOverlayController, Callable[[], GhostOverlayController]]
        ] = None,
        get_element_context: Optional[Callable[[], List[Dict[str, Any]]]] = None,
    ) -> None:
        self.safety_guard = safety_guard or SafetyGuard(SafetyLevel.NORMAL)
        self.audit_logger = audit_logger or get_logger()
        self.shadow_recorder = shadow_recorder or ShadowRecorder(
            capture_fn=capture_fn,
            get_screenshot_path_fn=get_screenshot_path_fn,
        )
        self._raw_overlay = ghost_overlay
        self._cached_overlay: Optional[GhostOverlayController] = None
        self.get_element_context = get_element_context
        self._mcp: Any = None

    @property
    def ghost_overlay(self) -> Optional[GhostOverlayController]:
        """Return the resolved GhostOverlayController (lazy-construct if factory)."""
        return self._resolve_overlay()

    def _resolve_overlay(self) -> Optional[GhostOverlayController]:
        """Resolve the overlay controller: instance, factory call, or None.

        V4: Accepts either a GhostOverlayController instance or a callable
        that returns one (e.g. OverlayControllerFactory). The callable is
        called exactly once and the result is cached.

        Uses duck-typing: if the raw value has a ``show_preview`` attribute,
        it is treated as an instance. Otherwise, if callable, it is treated
        as a factory.
        """
        if self._raw_overlay is None:
            return None
        # Duck-type: if it has show_preview, it's an overlay instance
        if hasattr(self._raw_overlay, "show_preview"):
            overlay = cast(GhostOverlayController, self._raw_overlay)
            self._cached_overlay = overlay
            return overlay
        # Callable: lazy construct once and cache
        if self._cached_overlay is None:
            self._cached_overlay = self._raw_overlay()
        return self._cached_overlay

    def bind_mcp(self, mcp: Any) -> None:
        """Store a reference to the MCP server for runtime interceptor guard checks."""
        self._mcp = mcp

    def assert_interceptor_active(self) -> None:
        """Assert that the global safety interceptor is still installed on the MCP.

        Raises InterceptorNotActiveError if the interceptor has been removed
        or replaced at runtime — a safety-critical bypass that would allow
        unguarded tool execution.
        """
        if self._mcp is None:
            return

        if not getattr(self._mcp, "_peekxd_global_safety_interceptor_installed", False):
            raise InterceptorNotActiveError(
                "Safety interceptor is not active: "
                "the global safety interceptor flag has been cleared. "
                "Tool dispatch is blocked."
            )

        interceptor_fn = getattr(self._mcp, "_peekxd_safety_interceptor_fn", None)
        if interceptor_fn is None or self._mcp.tool is not interceptor_fn:
            raise InterceptorNotActiveError(
                "Safety interceptor is not active: "
                "mcp.tool has been replaced from the intercepted version. "
                "Tool dispatch is blocked."
            )

    def wrap_tool(
        self,
        tool_name: str,
        func: Callable[..., Any],
    ) -> Callable[..., Dict[str, Any]]:
        """Wrap a tool function with safety classification and audit metadata."""

        @functools.wraps(func)
        def wrapped(*args: Any, **kwargs: Any) -> Dict[str, Any]:
            try:
                self.assert_interceptor_active()
            except InterceptorNotActiveError as exc:
                return self._interceptor_missing_response(tool_name, str(exc))

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
                # V4: enrich overlay request with snapshot element context
                if self.get_element_context is not None:
                    elements = self.get_element_context()
                    build_ghost_overlay_context(overlay_request, elements)
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
                self.safety_guard.check_action(tool_name, params)
            except PermissionDeniedError as exc:
                error_msg = str(exc)
                result: Dict[str, Any] = {
                    "success": False,
                    "blocked": True,
                    "error": error_msg,
                }
                entry = self.audit_logger.log_action(
                    tool_name,
                    params,
                    result=result.copy(),
                    error=error_msg,
                    zone=decision.zone.value,
                    executed=False,
                )
                result.update(self._metadata(decision, entry))
                return result

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

    def _interceptor_missing_response(
        self,
        tool_name: str,
        error_message: str,
    ) -> Dict[str, Any]:
        """Return a structured MCP error when the safety interceptor is missing."""
        result: Dict[str, Any] = {
            "success": False,
            "blocked": True,
            "error": error_message,
        }
        self.audit_logger.log_action(
            tool_name,
            {},
            result=result.copy(),
            error=error_message,
            zone="interceptor_missing",
            executed=False,
        )
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
            "safety_capability_version": MCP_SAFETY_CAPABILITY_VERSION,
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
    setattr(mcp, "_peekxd_safety_interceptor_fn", intercepted_tool)
    return mcp


def _dispatch_result(payload: Dict[str, Any], *, is_error: bool = False) -> Any:
    """Return a FastMCP-compatible dispatch result for synthetic guard responses."""
    try:
        from fastmcp.tools import ToolResult
    except ImportError:
        return payload

    return ToolResult(structured_content=payload, is_error=is_error)


def _append_dispatch_metadata(result: Any, metadata: Dict[str, Any]) -> Any:
    """Append safety metadata to common FastMCP or test dispatch result shapes."""
    if isinstance(result, dict):
        enriched = dict(result)
        enriched.update(metadata)
        return enriched

    structured_content = getattr(result, "structured_content", None)
    if isinstance(structured_content, dict):
        structured_content.update(metadata)
    return result


def _audit_payload_from_dispatch_result(result: Any) -> Dict[str, Any]:
    """Extract a safe audit payload from common dispatch result shapes."""
    if isinstance(result, dict):
        return dict(result)

    structured_content = getattr(result, "structured_content", None)
    if isinstance(structured_content, dict):
        return dict(structured_content)

    return {"success": True}


def install_dispatch_safety_guard(mcp: Any, middleware: SafetyMiddleware) -> Any:
    """Guard MCP tool calls at dispatch time.

    The registration interceptor protects tools that go through ``mcp.tool()``.
    This dispatch guard protects the final ``call_tool`` path as well, so tools
    injected directly into a server registry are still classified, blocked, and
    audited before execution.
    """
    if vars(mcp).get("_peekxd_dispatch_safety_guard_installed", False):
        return mcp
    if not hasattr(mcp, "call_tool"):
        return mcp

    original_call_tool = mcp.call_tool

    async def guarded_call_tool(
        name: str,
        arguments: Optional[Dict[str, Any]] = None,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        params = dict(arguments or {})
        try:
            middleware.assert_interceptor_active()
        except InterceptorNotActiveError as exc:
            response = middleware._interceptor_missing_response(name, str(exc))
            return _dispatch_result(response, is_error=True)

        decision = middleware.safety_guard.check_zone(name, params)
        if decision.zone == Zone.GHOST:
            response = middleware._blocked_response(name, params, decision)
            return _dispatch_result(response, is_error=True)

        try:
            middleware.safety_guard.check_action(name, params)
        except PermissionDeniedError as exc:
            error_msg = str(exc)
            response: Dict[str, Any] = {
                "success": False,
                "blocked": True,
                "error": error_msg,
            }
            entry = middleware.audit_logger.log_action(
                name,
                params,
                result=response.copy(),
                error=error_msg,
                zone=decision.zone.value,
                executed=False,
            )
            response.update(middleware._metadata(decision, entry))
            return _dispatch_result(response, is_error=True)

        try:
            result = await cast(
                Callable[..., Awaitable[Any]],
                original_call_tool,
            )(name, arguments, *args, **kwargs)
        except Exception as exc:
            middleware.audit_logger.log_action(
                name,
                params,
                result=decision.to_dict(),
                error=str(exc),
                zone=decision.zone.value,
                executed=False,
            )
            raise

        audit_result = _audit_payload_from_dispatch_result(result)
        entry = middleware.audit_logger.log_action(
            name,
            params,
            result=audit_result,
            zone=decision.zone.value,
            executed=True,
        )
        return _append_dispatch_metadata(result, middleware._metadata(decision, entry))

    setattr(mcp, "_peekxd_original_call_tool", original_call_tool)
    setattr(mcp, "call_tool", guarded_call_tool)
    setattr(mcp, "_peekxd_dispatch_safety_guard_installed", True)
    setattr(mcp, "_peekxd_dispatch_safety_guard_fn", guarded_call_tool)
    return mcp
