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

import fcntl
import hashlib
import json
import os
import secrets
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

from .envelope import ActionEnvelope, build_envelope
from .zones import (
    GhostActionClassification,
    RiskDecision,
    Zone,
    ZoneDecision,
)

DECISION_SCHEMA_VERSION = "PEEKXD-SAFETY-DECISION-1.0.0"

# Approval/claim state machine states (G3).
STATE_PENDING = "pending"
STATE_APPROVED = "approved"
STATE_CLAIMED = "claimed"
STATE_EXECUTED = "executed"
TERMINAL_STATES = frozenset({
    "denied", "expired", "blocked", "unknown_after_crash",
})

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
    envelope_digest: str = ""           # sha256 of the FULL canonical envelope
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
            "envelope_digest": self.envelope_digest,
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
    return hashlib.sha256(_canonical_params(params).encode()).hexdigest()


def _state_dir() -> Path:
    root = os.environ.get("PEEKXD_STATE_DIR")
    base = Path(root) if root else Path.home() / ".local" / "state" / "peekxd"
    return base / "approvals"


class ApprovalStore:
    """Persistent approval ledger (G3 canonical authority).

    State machine: PENDING → APPROVED → CLAIMED → EXECUTED with terminal
    DENIED / EXPIRED / BLOCKED / UNKNOWN_AFTER_CRASH. All transitions are
    serialized across PROCESSES via an OS-level ``fcntl.flock`` on a
    per-decision lockfile, so exactly one claim ever wins. A CLAIMED record
    is never auto-replayed after a crash; it must be explicitly resolved to
    UNKNOWN_AFTER_CRASH.
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
        except Exception as exc:
            # Fail closed: a corrupt/unreadable ledger record must never be
            # treated as an absent (or silently approvable) decision.
            raise DecisionLedgerError(
                f"approval ledger unreadable for {decision_id}: {exc}") from exc

    def save(self, record: Dict[str, Any]) -> None:
        # Unique per-writer tmp file: concurrent writers of DIFFERENT
        # decisions must never share one .tmp path; concurrent writers of
        # the SAME decision are serialized by the flock in approve/deny/
        # register/claim/mark_executed.
        target = self._path(record["decision_id"])
        tmp = target.with_suffix(f".tmp.{os.getpid()}.{uuid.uuid4().hex[:8]}")
        try:
            tmp.write_text(json.dumps(record, indent=2, sort_keys=True))
            os.replace(tmp, target)
        finally:
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass

    def _locked_update(self, decision_id: str, mutate,
                       required: bool = True) -> Dict[str, Any]:
        """Run ``mutate(rec)`` under the per-decision exclusive lock.

        With ``required=False`` a missing record is passed as ``None`` so
        idempotent creations (register) work inside the same lock.
        """
        with open(self._lock_path(decision_id), "a+") as lock_fh:
            fcntl.flock(lock_fh.fileno(), fcntl.LOCK_EX)
            try:
                rec = self.load(decision_id)
                if rec is None and required:
                    raise DecisionStateError(decision_id, "unknown decision")
                rec = mutate(rec)
                if rec is not None:
                    self.save(rec)
                return rec
            finally:
                fcntl.flock(lock_fh.fileno(), fcntl.LOCK_UN)

    def register(self, decision: SafetyDecision) -> None:
        """Persist a decision so approvals survive restarts."""
        def _register(rec: Optional[Dict[str, Any]]):
            if rec is not None:
                return None  # idempotent
            return {
                "decision_id": decision.decision_id,
                "action": decision.action,
                "params_digest": decision.params_digest,
                "envelope_digest": getattr(decision, "envelope_digest", ""),
                "zone": decision.zone,
                "ghost_classification": decision.ghost_classification,
                "policy_result": decision.policy_result,
                "approval_state": decision.required_approval_state or "none",
                "execution_nonce": decision.execution_nonce,
                "expiry": decision.expiry,
                "created_at": decision.created_at,
                "consumed_at": None,
                "approved_at": None,
                "claimed_at": None,
                "denied_at": None,
                "executed_at": None,
                "crashed_at": None,
            }
        self._locked_update(decision.decision_id, _register, required=False)

    # -- state transitions -------------------------------------------------

    def approve(self, decision_id: str) -> Dict[str, Any]:
        def _approve(rec: Dict[str, Any]) -> Dict[str, Any]:
            if rec.get("policy_result") not in ("require_approval", "allow", "allow_shadow"):
                # HARD_BLOCKED / fail-closed decisions can never be approved.
                raise DecisionStateError(
                    decision_id, f"not approvable (policy={rec.get('policy_result')})")
            if rec["approval_state"] in (STATE_CLAIMED, STATE_EXECUTED) or rec["approval_state"] in TERMINAL_STATES:
                raise DecisionStateError(
                    decision_id, f"replay rejected (state={rec['approval_state']})")
            if self._expired(rec):
                rec["approval_state"] = "expired"
                self.save(rec)
                raise DecisionStateError(decision_id, "approval window expired")
            rec["approval_state"] = "approved"
            rec["approved_at"] = time.time()
            return rec
        return self._locked_update(decision_id, _approve)

    def deny(self, decision_id: str) -> Dict[str, Any]:
        def _deny(rec: Dict[str, Any]) -> Dict[str, Any]:
            if rec["approval_state"] in (STATE_CLAIMED, STATE_EXECUTED) or rec["approval_state"] in TERMINAL_STATES:
                raise DecisionStateError(
                    decision_id, f"replay rejected (state={rec['approval_state']})")
            rec["approval_state"] = "denied"
            rec["denied_at"] = time.time()
            return rec
        return self._locked_update(decision_id, _deny)

    def mark_linked_consumed(
        self, decision_id: str, permit_decision_id: str,
    ) -> Dict[str, Any]:
        """Resolve a PENDING decision whose action was executed under a
        redeemed prior approval permit.

        Terminal: the record can never be approved or claimed afterwards,
        so no second execution can ever ride on this decision.
        """
        def _consume(rec: Dict[str, Any]) -> Dict[str, Any]:
            state = rec.get("approval_state")
            if state in (STATE_CLAIMED, STATE_EXECUTED) or state in TERMINAL_STATES:
                return rec  # already resolved; nothing to do
            rec["approval_state"] = "consumed"
            rec["consumed_at"] = time.time()
            rec["redeemed_permit_decision_id"] = permit_decision_id
            return rec
        return self._locked_update(decision_id, _consume)

    def _lock_path(self, decision_id: str) -> Path:
        return self._dir / f".{decision_id}.lock"

    @staticmethod
    def _replay_error(decision_id: str, state: Any) -> "DecisionStateError":
        return DecisionStateError(decision_id, f"replay rejected (state={state})")

    def claim(
        self,
        decision_id: str,
        expected_nonce: str,
        envelope_digest: str,
    ) -> Dict[str, Any]:
        """Atomically transition a decision into CLAIMED (G3).

        Serialized across PROCESSES via ``fcntl.flock`` on a per-decision
        lockfile: exactly one caller wins; every other caller fails with a
        :class:`DecisionStateError` BEFORE any side effect happens. The
        execution nonce AND the full envelope digest must match exactly.
        """
        with open(self._lock_path(decision_id), "a+") as lock_fh:
            fcntl.flock(lock_fh.fileno(), fcntl.LOCK_EX)
            try:
                rec = self._require(decision_id)
                state = rec.get("approval_state")
                if rec.get("consumed_at") is not None:
                    raise self._replay_error(decision_id, state)
                if state in (STATE_CLAIMED, STATE_EXECUTED) or state in TERMINAL_STATES:
                    raise self._replay_error(decision_id, state)
                if rec.get("execution_nonce") != expected_nonce:
                    raise DecisionStateError(
                        decision_id, "execution nonce mismatch")
                recorded_digest = str(rec.get("envelope_digest") or "")
                if recorded_digest and envelope_digest \
                        and recorded_digest != envelope_digest:
                    raise DecisionStateError(
                        decision_id, "envelope digest mismatch")
                if self._expired(rec):
                    rec["approval_state"] = "expired"
                    self.save(rec)
                    raise DecisionStateError(
                        decision_id, "approval window expired")

                policy = rec.get("policy_result")
                if policy == "require_approval":
                    if state != STATE_APPROVED:
                        raise DecisionStateError(
                            decision_id,
                            f"not approved for claim (state={state})")
                elif policy in ("allow", "allow_shadow"):
                    if state not in ("none", "", None, STATE_APPROVED):
                        raise DecisionStateError(
                            decision_id,
                            f"allow-path not claimable (state={state})")
                else:
                    rec["approval_state"] = "blocked"
                    self.save(rec)
                    raise DecisionStateError(
                        decision_id, f"policy {policy} can never be claimed")

                rec["approval_state"] = STATE_CLAIMED
                rec["claimed_at"] = time.time()
                rec["claim_pid"] = os.getpid()
                self.save(rec)
                return rec
            finally:
                fcntl.flock(lock_fh.fileno(), fcntl.LOCK_UN)

    def mark_executed(self, decision_id: str) -> Dict[str, Any]:
        """CLAIMED → EXECUTED. Valid only directly after a successful claim."""
        with open(self._lock_path(decision_id), "a+") as lock_fh:
            fcntl.flock(lock_fh.fileno(), fcntl.LOCK_EX)
            try:
                rec = self._require(decision_id)
                if rec.get("approval_state") != STATE_CLAIMED:
                    raise DecisionStateError(
                        decision_id,
                        f"cannot mark executed (state={rec.get('approval_state')})")
                rec["approval_state"] = STATE_EXECUTED
                rec["executed_at"] = time.time()
                rec["consumed_at"] = rec["executed_at"]
                self.save(rec)
                return rec
            finally:
                fcntl.flock(lock_fh.fileno(), fcntl.LOCK_UN)

    def mark_unknown_after_crash(self, decision_id: str) -> Dict[str, Any]:
        """Explicitly resolve a stuck CLAIMED record to its terminal state.

        Claimed records are NEVER auto-replayed: after a crash between claim
        and execute the side-effect state is unknown, so the record becomes
        terminally UNKNOWN_AFTER_CRASH and can never execute again.
        """
        with open(self._lock_path(decision_id), "a+") as lock_fh:
            fcntl.flock(lock_fh.fileno(), fcntl.LOCK_EX)
            try:
                rec = self._require(decision_id)
                if rec.get("approval_state") != STATE_CLAIMED:
                    raise DecisionStateError(
                        decision_id,
                        f"not claim-stuck (state={rec.get('approval_state')})")
                rec["approval_state"] = "unknown_after_crash"
                rec["crashed_at"] = time.time()
                self.save(rec)
                return rec
            finally:
                fcntl.flock(lock_fh.fileno(), fcntl.LOCK_UN)

    def consume(self, decision_id: str) -> bool:
        """Backward-compatible single-use consumption.

        Thin wrapper over the atomic claim state machine. Returns False on
        replay/state errors; ledger READ FAILURES still RAISE (fail closed).
        """
        rec = self.load(decision_id)
        if rec is None:
            return False
        try:
            self.claim(
                decision_id,
                str(rec.get("execution_nonce")),
                str(rec.get("envelope_digest") or ""),
            )
            self.mark_executed(decision_id)
            return True
        except DecisionStateError:
            return False

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


class DecisionLedgerError(Exception):
    """The approval ledger itself is missing/corrupt/unreadable — fail closed."""


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
        envelope: Optional[ActionEnvelope] = None,
        correlation_id: str = "",
    ) -> SafetyDecision:
        """The single canonical evaluation (G3).

        Builds/consumes a canonical :class:`ActionEnvelope` and binds the
        returned decision to its FULL-envelope sha256 digest via
        ``envelope_digest``; ``decision_id`` + ``execution_nonce`` remain the
        redemption binding recorded in the ledger.
        """
        risk: RiskDecision = ZoneDecision.decide(action, params)

        classification = ZoneDecision.classify_ghost_action(
            action, params, risk.risk_factors, force_ghost=self.force_ghost,
        )

        correlation = (
            correlation_id
            or f"ev_{self.session_correlation}_{secrets.token_hex(4)}"
        )
        nonce = secrets.token_hex(16)

        if self.force_ghost:
            risk = RiskDecision(
                zone=Zone.GHOST,
                risk_level="forced_preview",
                risk_factors=["force_ghost_enabled"],
                reason="GHOST mode forced via --ghost flag",
            )

        # Canonical envelope: bound to the final assigned zone so the digest
        # covers the complete normalized action description. The random
        # per-decision correlation token is deliberately EXCLUDED from the
        # binding payload: two evaluations of the identical action must
        # produce the identical envelope digest (exact-binding redemption).
        if envelope is None:
            envelope = build_envelope(
                action=action,
                params=params,
                entry_point=entry_point,
                target_application=target_application,
                target_window=target_window,
                zone=risk.zone.value,
                correlation_id="",  # stable across decisions
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
            envelope_digest=envelope.digest(),
        )

        # HARD_BLOCKED_GHOST can never execute through ANY entry point —
        # but only for actions that actually need the ghost-approval flow.
        # A zero-risk DIRECT allow-path action (e.g. read-only observation)
        # is not a ghost action at all: its zone decides below.
        if (classification.classification
                == GhostActionClassification.HARD_BLOCKED_GHOST
                and risk.zone == Zone.GHOST):
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

    def claim(self, decision: SafetyDecision) -> Dict[str, Any]:
        """Atomically CLAIM a decision (G3). Raises on replay/mismatch."""
        return self.store.claim(
            decision.decision_id,
            decision.execution_nonce,
            getattr(decision, "envelope_digest", ""),
        )


_GATE: Optional[SafetyDecisionGate] = None


def get_gate(force_ghost: bool = False) -> SafetyDecisionGate:
    """Process-wide canonical gate (one policy instance per runtime).

    ``force_ghost`` is honored on EVERY call: if the singleton already
    exists without it, its flag is updated so a later ``--ghost`` request
    is never silently downgraded to normal policy.
    """
    global _GATE
    if _GATE is None:
        _GATE = SafetyDecisionGate(force_ghost=force_ghost)
    elif force_ghost and not _GATE.force_ghost:
        _GATE.force_ghost = True
    return _GATE


def reset_gate() -> None:
    global _GATE
    _GATE = None
