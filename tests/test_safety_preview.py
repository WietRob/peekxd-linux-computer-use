"""Tests for SafetyGuard.preview() and the peekxd_preview_action MCP tool."""

from unittest.mock import MagicMock

from peekxd.core.audit import AuditLogger
from peekxd.core.safety import SafetyGuard, SafetyLevel
from peekxd.core.zones import RiskDecision, Zone
from peekxd.mcp_server.middleware import SafetyMiddleware


class TestSafetyGuardPreview:
    """TDD: SafetyGuard.preview() returns a safe simulation without side effects."""

    def test_preview_returns_structured_simulation_envelope(self):
        """preview() must return preview=True, action, params, and a note."""
        guard = SafetyGuard(SafetyLevel.NORMAL)
        result = guard.preview("type_text", {"text": "hello world"})

        assert result["preview"] is True
        assert result["action"] == "type_text"
        assert result["params"] == {"text": "hello world"}
        assert "simulation" in result["note"].lower()
        assert "no real action" in result["note"].lower()

    def test_preview_logs_to_preview_log_with_simulated_flag(self):
        """preview() must record the simulated action in preview_log."""
        guard = SafetyGuard(SafetyLevel.NORMAL)
        assert len(guard.preview_log) == 0

        guard.preview("click", {"x": 100, "y": 200})

        assert len(guard.preview_log) == 1
        entry = guard.preview_log[0]
        assert entry["action"] == "click"
        assert entry["params"] == {"x": 100, "y": 200}
        assert entry["risk"] == "preview"
        assert entry["executed"] is False
        assert entry["simulated"] is True

    def test_preview_is_read_only_does_not_mutate_state(self):
        """preview() must not execute any real action or mutate external state."""
        guard = SafetyGuard(SafetyLevel.STRICT)
        prior_log = len(guard.preview_log)

        # Call preview with a dangerous action — should NOT raise
        result = guard.preview("type_text", {"text": "rm -rf /"})

        assert result["preview"] is True
        # No PermissionDeniedError raised — preview is always safe
        # Log only grew by the preview entry, not by any check_action log
        assert len(guard.preview_log) == prior_log + 1

    def test_preview_does_not_call_check_action(self):
        """preview() bypasses check_action entirely — it never executes."""
        guard = SafetyGuard(SafetyLevel.STRICT)
        # Verify preview with destructive text does not raise
        result = guard.preview("type_text", {"text": "sudo rm -rf /"})
        assert result["preview"] is True
        assert result["action"] == "type_text"


class TestPreviewActionMiddleware:
    """TDD: peekxd_preview_action passes through SafetyMiddleware without blocking.

    The middleware must allow a preview-only tool (like peekxd_preview_action)
    to execute because it's a read-only observational tool, even when the
    action being previewed would normally trigger GHOST classification.
    """

    def test_preview_action_middleware_allows_read_only_tool(self):
        """A preview tool should pass through middleware with zone+risk metadata.

        peekxd_preview_action is a read-only tool (classified as DIRECT by
        ZoneDecision). Even when its params contain a dangerous nested action,
        the tool itself is safe and must be allowed to execute.
        """
        guard = MagicMock()
        guard.check_zone.return_value = RiskDecision(
            zone=Zone.DIRECT,
            risk_level="safe",
            risk_factors=[],
            reason="Read-only observation action",
        )
        guard.check_action.return_value = True
        guard.preview.return_value = {
            "preview": True,
            "action": "type_text",
            "params": {"text": "rm -rf /tmp"},
            "note": "This is a simulation.",
        }
        logger = AuditLogger(session_id="mcp-preview-test")

        middleware = SafetyMiddleware(safety_guard=guard, audit_logger=logger)

        def peekxd_preview_action(action: str, params: dict) -> dict:
            preview_result = guard.preview(action, params)
            zone_decision = guard.check_zone(action, params)
            return {
                "preview": preview_result,
                "zone_decision": zone_decision.to_dict(),
                "risk_metadata": {
                    "zone": zone_decision.zone.value,
                    "risk_level": zone_decision.risk_level,
                    "risk_factors": zone_decision.risk_factors,
                },
            }

        wrapped = middleware.wrap_tool("peekxd_preview_action", peekxd_preview_action)
        result = wrapped(
            action="type_text",
            params={"text": "rm -rf /tmp"},
        )

        # The middleware must let this through — it's a DIRECT zone tool
        # The tool function returns a dict, so _envelope_result passes it through
        assert result["zone"] == "direct"
        assert result["risk_level"] == "safe"
        assert result["audit_id"] == "mcp-preview-test:0"
        assert result["preview"]["preview"] is True

        # Verify the middleware called both check_zone and check_action
        guard.check_zone.assert_called()
        guard.check_action.assert_called()

    def test_preview_action_middleware_preserves_preview_and_zone_metadata(self):
        """The wrapped preview tool response must carry both preview data and
        safety zone/risk metadata from the middleware envelope.
        """
        guard = MagicMock()
        guard.check_zone.return_value = RiskDecision(
            zone=Zone.DIRECT,
            risk_level="safe",
            risk_factors=[],
            reason="Read-only observation action",
        )
        guard.check_action.return_value = True
        guard.preview.return_value = {
            "preview": True,
            "action": "click",
            "params": {"x": 42, "y": 99},
            "note": "This is a simulation — no real action was performed.",
        }
        logger = AuditLogger(session_id="mcp-preview-test")

        middleware = SafetyMiddleware(safety_guard=guard, audit_logger=logger)

        def peekxd_preview_action(action: str, params: dict) -> dict:
            preview_result = guard.preview(action, params)
            zone_decision = guard.check_zone(action, params)
            return {
                "preview": preview_result,
                "zone_decision": zone_decision.to_dict(),
                "risk_metadata": {
                    "zone": zone_decision.zone.value,
                    "risk_level": zone_decision.risk_level,
                    "risk_factors": zone_decision.risk_factors,
                },
            }

        wrapped = middleware.wrap_tool("peekxd_preview_action", peekxd_preview_action)
        result = wrapped(action="click", params={"x": 42, "y": 99})

        assert result["zone"] == "direct"
        assert result["risk_level"] == "safe"
        assert result["audit_id"] == "mcp-preview-test:0"
        assert result["preview"]["preview"] is True
        assert result["preview"]["action"] == "click"
