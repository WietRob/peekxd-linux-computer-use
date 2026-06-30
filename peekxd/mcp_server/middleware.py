"""Safety middleware for peekxd MCP tools."""

from __future__ import annotations

import functools
from typing import Any, Callable, Dict, Optional

from ..core.audit import AuditLogger, get_logger
from ..core.safety import SafetyGuard, SafetyLevel
from ..core.shadow import ShadowRecorder
from ..core.zones import RiskDecision, Zone


class SafetyMiddleware:
    """Apply SafetyGuard zone checks and audit logging to MCP tool calls."""

    def __init__(
        self,
        safety_guard: Optional[SafetyGuard] = None,
        audit_logger: Optional[AuditLogger] = None,
        shadow_recorder: Optional[ShadowRecorder] = None,
    ) -> None:
        self.safety_guard = safety_guard or SafetyGuard(SafetyLevel.NORMAL)
        self.audit_logger = audit_logger or get_logger()
        self.shadow_recorder = shadow_recorder or ShadowRecorder()

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
                return self._blocked_response(tool_name, params, decision)

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
            entry = self.audit_logger.log_action(
                tool_name,
                params,
                result=result.copy(),
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
    ) -> Dict[str, Any]:
        error = f"Blocked by SafetyGuard: {decision.reason or 'GHOST zone action'}"
        result = {
            "success": False,
            "blocked": True,
            "error": error,
            "risk_factors": decision.risk_factors,
        }
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
