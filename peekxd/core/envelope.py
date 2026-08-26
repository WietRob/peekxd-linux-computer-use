"""Canonical ActionEnvelope (G3).

Every safety-relevant action is bound to a canonical, frozen envelope before
a :class:`~peekxd.core.decision.SafetyDecisionGate` decision is made. The
envelope captures the COMPLETE normalized payload — not just a params digest —
so approvals and executions are bound to the exact action they were granted
for.

``digest()`` is the sha256 of the full canonical envelope JSON and is the
binding token recorded in the approval ledger and on every SafetyDecision.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Dict

#: Version of the policy/envelope schema — bump when binding semantics change.
ENVELOPE_POLICY_VERSION = "PEEKXD-ACTION-ENVELOPE-1.0.0"


def _normalize(value: Any) -> Any:
    """Recursively normalize a payload into JSON-canonical form."""
    if isinstance(value, dict):
        return {str(k): _normalize(value[k]) for k in sorted(value, key=str)}
    if isinstance(value, (list, tuple)):
        return [_normalize(v) for v in value]
    if isinstance(value, (set, frozenset)):
        return sorted((_normalize(v) for v in value), key=repr)
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    return str(value)  # deterministic fallback for non-JSON primitives


@dataclass(frozen=True)
class ActionEnvelope:
    """Immutable canonical description of one to-be-executed action."""

    action: str
    params: Dict[str, Any] = field(default_factory=dict)
    target_application: str = ""
    target_window: str = ""
    zone: str = ""
    policy_version: str = ENVELOPE_POLICY_VERSION
    entry_point: str = ""          # cli | macro | mcp | orchestrator | bridge
    correlation_id: str = ""       # task/session correlation id

    def canonical_json(self) -> str:
        """Return the canonical (sorted-key, normalized) JSON representation."""
        payload = {
            "policy_version": self.policy_version,
            "action": self.action,
            "params": _normalize(self.params),
            "target_application": self.target_application,
            "target_window": self.target_window,
            "zone": self.zone,
            "entry_point": self.entry_point,
            "correlation_id": self.correlation_id,
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    def digest(self) -> str:
        """sha256 hex digest of the FULL canonical envelope JSON."""
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "policy_version": self.policy_version,
            "action": self.action,
            "params": _normalize(self.params),
            "target_application": self.target_application,
            "target_window": self.target_window,
            "zone": self.zone,
            "entry_point": self.entry_point,
            "correlation_id": self.correlation_id,
            "envelope_digest": self.digest(),
        }


def build_envelope(
    action: str,
    params: Dict[str, Any],
    entry_point: str = "",
    target_application: str = "",
    target_window: str = "",
    zone: str = "",
    correlation_id: str = "",
) -> ActionEnvelope:
    """Build a normalized ActionEnvelope from raw call-site inputs."""
    return ActionEnvelope(
        action=str(action),
        params=_normalize(dict(params or {})),
        target_application=target_application or "",
        target_window=target_window or "",
        zone=zone or "",
        entry_point=entry_point or "",
        correlation_id=correlation_id or "",
    )
