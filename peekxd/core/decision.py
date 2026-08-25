"""Canonical SafetyDecision boundary (G3, Softbox).

Every PeekXD action entry point — direct CLI, macro runner, MCP tools,
agent orchestrator, and any Conduvera bridge — must obtain exactly one
SafetyDecision from :class:`SafetyDecisionGate` before executing. The gate
is the ONLY place that combines:

- zone assignment (:class:`~peekxd.core.zones.ZoneDecision`);
- Ghost classification (APPROVABLE / HARD_BLOCKED);
- destructive-NORMAL fail-closed rule;
- approval state (pending / approved-once / denied / expired / consumed);
- execution nonce and expiry;
- evidence correlation id.

No execution path may duplicate this logic. Denial, timeout and replay
execute nothing.
"""

from __future__ import annotations

import json
import os
import secrets
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

from .zones import (
    GhostActionClassification,
    RiskDecision,
    Zone,
    ZoneDecision,
)

DECISION_SCHEMA_VERSION = "PEEKXD-SAFETY-DECISION-1.0.0"

#: Approval lifetime for APPROVABLE_GHOST decisions (seconds).
DEFAULT_APPROVAL_TTL_SECONDS = 300


@dataclass
class SafetyDecision:
    """The single canonical decision object every execution path consumes."""

    decision_id: str
    action: str
    target_application: str = ""
    target_window: str = ""
    zone: str = ""                      # ghost | shadow | guided | direct
    ghost_classification: str = ""      # approvable_ghost | hard_blocked_ghost | ""
    policy_result: str = ""             # allow_shadow | require_approval |
                                        # hard_blocked | deny | fail_closed
    required_approval_state: str = ""   # none | pending | approved | denied |
                                        # expired | consumed
    expiry: Optional[float] = None      # unix ts after which approval is void
    execution_nonce: str = ""           # single-use token bound to the payload
    reason: str = ""
    evidence_correlation_id: str = ""
    entry_point: str = ""               # cli | macro | mcp | orchestrator | bridge
    params_digest: str = ""             # sha256 of canonical params JSON
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": DECISION_SCHEMA_VERSION,
            "decision_id": self.decision_id,
            "action": self.action,
            "target_application": self.target_application,
            "target_window": self.target_window,
            "zone": self.zone,
            "ghost_classification": self.ghost_classification,
            "policy_result": self.policy_result,
            "required_approval_state": self.required_approval_state,
            "expiry": self.expiry,
            "execution_nonce": self.execution_nonce,
            "reason": self.reason,
            "evidence_correlation_id": self.evidence_correlation_id,
            "entry_point": self.entry_point,
            "params_digest": self.params_digest,
            "created_at": self.created_at,
        }


class DecisionDeniedError(PermissionError):
    """Raised when an action must not execute under the canonical policy."""

    def __init__(self, decision: SafetyDecision):
        self.decision = decision
        super().__init__(
            f"[SAFETY-DECISION {decision.decision_id}] "
            f"{decision.policy_result}: {decision.reason}"
        )


def _canonical_params(params: Dict[str, Any]) -> str:
    try:
        return json.dumps(params, sort_keys=True, default=str)
    except Exception:
        return repr(sorted((k, str(v)) for k, v in params.items()))


def _digest_params(params: Dict[str, Any]) -> str:
    import hashlib

    return hashlib.sha256(_canonical_params(params).encode()).hexdigest()


def _state_dir() -> Path:
    root = os.environ.get("PEEKXD_STATE_DIR")
    base = Path(root) if root else Path.home() / ".local" / "state" / "peekxd"
    return base / "approvals"


class ApprovalStore:
    """Persistent approval ledger — pending/approved/denied/consumed.

    State survives component restarts. An approval permits EXACTLY ONE
    execution; replay and duplicate delivery are rejected.
    """

    def __init__(self, directory: Optional[Path] = None):
        self._dir = Path(directory) if directory else _state_dir()
        self._dir.mkdir(parents=True, exist_ok=True)

    def _path(self, decision_id: str) -> Path:
        return self._dir / f"{decision_id}.json"

    def load(self, decision_id: str) -> Optional[Dict[str, Any]]:
        p = self._path(decision_id)
        if not p.exists():
            return None
        try:
            return json.loads(p.read_text())
        except Exception:
            return None

    def save(self, record: Dict[str, Any]) -> None:
        tmp = self._path(record["decision_id"]).with_suffix(".tmp")
        tmp.write_text(json.dumps(record, indent=2, sort_keys=True))
        tmp.replace(self._path(record["decision_id"]))

    def register(self, decision: SafetyDecision) -> None:
        """Persist a decision so approvals survive restarts."""
        if self.load(decision.decision_id) is not None:
            return  # idempotent
        self.save({
            "decision_id": decision.decision_id,
            "action": decision.action,
            "params_digest": decision.params_digest,
            "zone": decision.zone,
            "ghost_classification": decision.ghost_classification,
            "policy_result": decision.policy_result,
            "approval_state": decision.required_approval_state or "none",
            "execution_nonce": decision.execution_nonce,
            "expiry": decision.expiry,
            "created_at": decision.created_at,
            "consumed_at": None,
            "approved_at": None,
            "denied_at": None,
            "executed_at": None,
        })

    # -- state transitions -------------------------------------------------

    def approve(self, decision_id: str) -> Dict[str, Any]:
        rec = self._require(decision_id)
        if rec.get("policy_result") != "require_approval":
            # HARD_BLOCKED / allow-path decisions cannot be approved
            raise DecisionStateError(
                decision_id, f"not approvable (policy={rec.get('policy_result')})")
        if rec["approval_state"] == "consumed":
            raise DecisionStateError(decision_id, "already consumed")
        if rec["approval_state"] == "denied":
            raise DecisionStateError(decision_id, "already denied")
        if rec["approval_state"] == "approved":
            # duplicate approval delivery is rejected — exactly-once semantics
            raise DecisionStateError(decision_id, "already approved")
        if self._expired(rec):
            rec["approval_state"] = "expired"
            self.save(rec)
            raise DecisionStateError(decision_id, "approval window expired")
        rec["approval_state"] = "approved"
        rec["approved_at"] = time.time()
        self.save(rec)
        return rec

    def deny(self, decision_id: str) -> Dict[str, Any]:
        rec = self._require(decision_id)
        if rec["approval_state"] == "consumed":
            raise DecisionStateError(decision_id, "already consumed")
        rec["approval_state"] = "denied"
        rec["denied_at"] = time.time()
        self.save(rec)
        return rec

    def consume(self, decision_id: str) -> bool:
        """Mark a decision as executed. Returns False on replay.

        Approval-required decisions must be 'approved'; allow-paths
        (shadow/direct) are consumed directly from state 'none'.
        """
        rec = self._require(decision_id)
        if rec.get("consumed_at") is not None:
            return False  # replay rejected
        if rec["approval_state"] not in ("approved", "none"):
            return False
        if self._expired(rec):
            rec["approval_state"] = "expired"
            self.save(rec)
            return False
        rec["consumed_at"] = time.time()
        rec["executed_at"] = rec["consumed_at"]
        rec["approval_state"] = "consumed"
        self.save(rec)
        return True

    def find_approved_unconsumed(
        self, action: str, params_digest: str,
    ) -> Optional[Dict[str, Any]]:
        """Return an approved-but-not-consumed record matching action+payload,
        or None. Used to redeem a prior out-of-band approval."""
        import glob as _glob
        for p in sorted(_glob.glob(str(self._dir / "*.json"))):
            try:
                rec = json.loads(Path(p).read_text())
            except Exception:
                continue
            if (rec.get("action") == action
                    and rec.get("params_digest") == params_digest
                    and rec.get("approval_state") == "approved"
                    and rec.get("consumed_at") is None
                    and not self._expired(rec)):
                return rec
        return None

    # -- helpers -----------------------------------------------------------

    @staticmethod
    def _expired(rec: Dict[str, Any]) -> bool:
        exp = rec.get("expiry")
        return exp is not None and time.time() > float(exp)

    def _require(self, decision_id: str) -> Dict[str, Any]:
        rec = self.load(decision_id)
        if rec is None:
            raise DecisionStateError(decision_id, "unknown decision")
        return rec


class DecisionStateError(Exception):
    def __init__(self, decision_id: str, why: str):
        self.decision_id = decision_id
        super().__init__(f"decision {decision_id}: {why}")


class SafetyDecisionGate:
    """THE one safety boundary. Evaluate → authorize → consume."""

    def __init__(
        self,
        approval_store: Optional[ApprovalStore] = None,
        force_ghost: bool = False,
        approval_ttl: int = DEFAULT_APPROVAL_TTL_SECONDS,
        confirmable: bool = False,
    ):
        self.store = approval_store or ApprovalStore()
        self.force_ghost = force_ghost
        self.approval_ttl = approval_ttl
        # confirmable=True mirrors the orchestrator's
        # _should_route_shadow_to_confirmable_ghost rule: zero-risk actions in
        # the approvable set are routed to the confirmable-ghost flow instead
        # of executing directly (Softbox V4).
        self.confirmable = confirmable
        self.session_correlation = uuid.uuid4().hex[:12]

    # -- evaluate ----------------------------------------------------------

    def evaluate(
        self,
        action: str,
        params: Dict[str, Any],
        entry_point: str = "",
        target_application: str = "",
        target_window: str = "",
    ) -> SafetyDecision:
        risk: RiskDecision = ZoneDecision.decide(action, params)

        classification = ZoneDecision.classify_ghost_action(
            action, params, risk.risk_factors, force_ghost=self.force_ghost,
        )

        correlation = (
            f"ev_{self.session_correlation}_{secrets.token_hex(4)}"
        )
        nonce = secrets.token_hex(16)

        if self.force_ghost:
            risk = RiskDecision(
                zone=Zone.GHOST,
                risk_level="forced_preview",
                risk_factors=["force_ghost_enabled"],
                reason="GHOST mode forced via --ghost flag",
            )

        common: Dict[str, Any] = dict(
            decision_id=f"dec_{uuid.uuid4().hex}",
            action=action,
            target_application=target_application,
            target_window=target_window,
            zone=risk.zone.value,
            ghost_classification=classification.classification.value,
            execution_nonce=nonce,
            reason=risk.reason,
            evidence_correlation_id=correlation,
            entry_point=entry_point,
            params_digest=_digest_params(params),
        )

        # HARD_BLOCKED_GHOST can never execute through ANY entry point.
        if (classification.classification
                == GhostActionClassification.HARD_BLOCKED_GHOST):
            decision = SafetyDecision(
                policy_result="hard_blocked",
                required_approval_state="none",
                expiry=None,
                **common,
            )
            self.store.register(decision)
            return decision

        if risk.zone == Zone.GHOST:
            # APPROVABLE_GHOST: pending until explicit per-decision approval.
            decision = SafetyDecision(
                policy_result="require_approval",
                required_approval_state="pending",
                expiry=time.time() + self.approval_ttl,
                **common,
            )
            self.store.register(decision)
            return decision

        if (
            self.confirmable
            and risk.zone == Zone.SHADOW
            and not risk.risk_factors
            and classification.classification
            == GhostActionClassification.APPROVABLE_GHOST
        ):
            # Confirmable-ghost routing (Softbox V4): zero-risk action in the
            # approvable set requires explicit approval before one execution.
            decision = SafetyDecision(
                policy_result="require_approval",
                required_approval_state="pending",
                expiry=time.time() + self.approval_ttl,
                **{**common, "ghost_classification":
                   GhostActionClassification.APPROVABLE_GHOST.value},
            )
            self.store.register(decision)
            return decision

        # Destructive content classified outside GHOST must fail closed.
        # ZoneDecision routes destructive text into GHOST already; this is the
        # belt-and-braces guard for future policy changes.
        if risk.risk_level == "destructive":
            decision = SafetyDecision(
                policy_result="fail_closed",
                required_approval_state="none",
                expiry=None,
                **common,
            )
            self.store.register(decision)
            return decision

        if risk.zone in (Zone.SHADOW, Zone.DIRECT, Zone.GUIDED):
            decision = SafetyDecision(
                policy_result=(
                    "allow_shadow" if risk.zone == Zone.SHADOW else "allow"
                ),
                required_approval_state="none",
                expiry=None,
                **common,
            )
            self.store.register(decision)
            return decision

        # Unknown zone: fail closed.
        decision = SafetyDecision(
            policy_result="fail_closed",
            required_approval_state="none",
            expiry=None,
            **common,
        )
        self.store.register(decision)
        return decision

    # -- authorize / consume -------------------------------------------------

    def is_execution_allowed(self, decision: SafetyDecision) -> bool:
        """SHADOW/DIRECT may run immediately; everything else needs approval."""
        return decision.policy_result in ("allow", "allow_shadow")

    def authorize(self, decision: SafetyDecision) -> bool:
        """Approve a pending decision. Exactly-once semantics enforced later
        by :meth:`consume`."""
        try:
            self.store.approve(decision.decision_id)
            return True
        except DecisionStateError:
            return False

    def deny(self, decision: SafetyDecision) -> bool:
        try:
            self.store.deny(decision.decision_id)
            return True
        except DecisionStateError:
            return False

    def consume(self, decision: SafetyDecision) -> bool:
        """Consume the approval right before executing. Replay → False."""
        return self.store.consume(decision.decision_id)


_GATE: Optional[SafetyDecisionGate] = None


def get_gate(force_ghost: bool = False) -> SafetyDecisionGate:
    """Process-wide canonical gate (one policy instance per runtime)."""
    global _GATE
    if _GATE is None:
        _GATE = SafetyDecisionGate(force_ghost=force_ghost)
    return _GATE


def reset_gate() -> None:
    global _GATE
    _GATE = None
