"""SafetyExecutor — the ONLY component allowed to reach raw execution (G3).

Every autonomous path (MCP tools, agent orchestrator, macro sequences, direct
CLI action commands) must run its raw input-provider / Hermes-tool call through
:meth:`SafetyExecutor.execute`. The executor:

1. verifies gate availability and decision well-formedness (else BLOCKS);
2. checks the approval expiry;
3. performs the atomic APPROVED → CLAIMED transition in the ledger
   (allow-path SHADOW/DIRECT go PENDING/none → CLAIMED directly) — across
   processes exactly ONE claim ever wins, and a losing claim fails BEFORE any
   side effect;
4. runs the raw action callable;
5. marks the record EXECUTED. On crash between claim and execute the record
   stays CLAIMED and is never replayed (terminal UNKNOWN_AFTER_CRASH only via
   explicit resolution).

Any ledger read/write failure blocks execution — it never degrades to
"continue without safety".
"""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, Optional

from .decision import (
    DecisionDeniedError,
    DecisionLedgerError,
    DecisionStateError,
    SafetyDecision,
    SafetyDecisionGate,
    get_gate,
)
from .envelope import ActionEnvelope


class SafetyExecutionBlocked(PermissionError):
    """Raised when the executor refuses to run an action (fail closed)."""

    def __init__(self, why: str, decision: Optional[SafetyDecision] = None):
        self.decision = decision
        super().__init__(f"[SAFETY-EXECUTOR] {why}")


def _owner_disabled() -> bool:
    """Owner kill switch (2026-08-26): PeekXD Computer Use INSTALLED_DISABLED.

    In-process execution (SafetyExecutor) also fails closed while an
    OWNER-DISABLED marker exists. Bypass requires the explicit per-run
    Owner authorization env (PEEKXD_OWNER_AUTHORIZED_RUN=1).
    """
    import os as _os
    from pathlib import Path as _Path

    if _os.environ.get("PEEKXD_OWNER_AUTHORIZED_RUN") == "1":
        return False
    markers = (
        _Path.home() / ".local" / "state" / "peekxd" / "OWNER-DISABLED",
        _Path(__file__).resolve().parent.parent / "OWNER-DISABLED",
    )
    return any(m.exists() for m in markers)


class SafetyExecutor:
    """Single raw-execution boundary. Nothing else may touch the provider."""

    def __init__(self, gate: Optional[SafetyDecisionGate] = None):
        # A missing/malformed gate is a hard block at execute() time.
        self.gate = gate

    # ------------------------------------------------------------------
    def _require_gate(self) -> SafetyDecisionGate:
        gate = self.gate
        if gate is None:
            try:
                gate = get_gate()
            except Exception as exc:  # pragma: no cover - defensive
                raise SafetyExecutionBlocked(
                    f"safety gate unavailable: {exc}") from exc
        if not isinstance(gate, SafetyDecisionGate) or not hasattr(gate, "store"):
            raise SafetyExecutionBlocked("malformed safety gate")
        return gate

    @staticmethod
    def _require_well_formed(decision: Any) -> SafetyDecision:
        if not isinstance(decision, SafetyDecision):
            raise SafetyExecutionBlocked(f"malformed decision object: {decision!r}")
        for attr in ("decision_id", "execution_nonce", "policy_result"):
            if not getattr(decision, attr, ""):
                raise SafetyExecutionBlocked(
                    f"decision missing {attr}", decision)
        return decision

    # ------------------------------------------------------------------
    def execute(
        self,
        decision: SafetyDecision,
        envelope: Optional[ActionEnvelope],
        runner: Callable[[], Any],
    ) -> Any:
        """Claim + run + mark-executed. Raises instead of executing unsafely."""
        if _owner_disabled():
            raise SafetyExecutionBlocked(
                "PEEKXD DISABLED BY OWNER (2026-08-26): computer use is "
                "INSTALLED_DISABLED; execution requires explicit per-run "
                "Owner authorization (PEEKXD_OWNER_AUTHORIZED_RUN=1).")
        gate = self._require_gate()
        decision = self._require_well_formed(decision)

        if decision.policy_result in ("hard_blocked", "fail_closed", "deny"):
            raise DecisionDeniedError(decision)

        # Envelope binding check: when the decision carries a canonical
        # envelope digest and the caller supplies an envelope, they must
        # match exactly — otherwise the claimed approval would not bind
        # the payload actually executed (fail closed).
        if envelope is not None:
            recorded = getattr(decision, "envelope_digest", "")
            if recorded and envelope.digest() != recorded:
                raise SafetyExecutionBlocked(
                    "caller envelope digest does not match decision binding",
                    decision,
                )

        expiry = getattr(decision, "expiry", None)
        if expiry is not None and time.time() > float(expiry):
            try:
                rec = gate.store.load(decision.decision_id)
                if rec is not None:
                    rec["approval_state"] = "expired"
                    gate.store.save(rec)
            except DecisionLedgerError:
                pass  # surfaced by the claim below
            raise DecisionStateError(decision.decision_id, "approval window expired")

        # Atomic APPROVED→CLAIMED (allow paths: none→CLAIMED). Exactly one
        # process wins; every loser fails BEFORE the side effect.
        try:
            gate.claim(decision)
        except (DecisionStateError, DecisionLedgerError):
            raise
        except OSError as exc:
            raise DecisionLedgerError(
                f"ledger claim failed for {decision.decision_id}: {exc}") from exc

        try:
            result = runner()
        except BaseException:
            # Crash semantics: the record stays CLAIMED — never auto-replayed.
            raise
        gate.store.mark_executed(decision.decision_id)
        return result

    async def execute_async(
        self,
        decision: SafetyDecision,
        envelope: Optional[ActionEnvelope],
        runner: Callable[[], Any],
    ) -> Any:
        """Async variant of :meth:`execute` for async dispatch paths.

        ``runner`` may be a plain callable or return an awaitable. The claim,
        expiry and well-formedness semantics are identical to :meth:`execute`.
        """
        import inspect
        import asyncio

        gate = self._require_gate()
        decision = self._require_well_formed(decision)

        if decision.policy_result in ("hard_blocked", "fail_closed", "deny"):
            raise DecisionDeniedError(decision)

        expiry = getattr(decision, "expiry", None)
        if expiry is not None and time.time() > float(expiry):
            raise DecisionStateError(decision.decision_id, "approval window expired")

        try:
            gate.claim(decision)
        except (DecisionStateError, DecisionLedgerError):
            raise
        except OSError as exc:
            raise DecisionLedgerError(
                f"ledger claim failed for {decision.decision_id}: {exc}") from exc

        outcome = runner()
        if inspect.isawaitable(outcome):
            outcome = await outcome
        gate.store.mark_executed(decision.decision_id)
        return outcome

    # ------------------------------------------------------------------
    def evaluate_and_execute(
        self,
        action: str,
        params: Dict[str, Any],
        entry_point: str,
        runner: Callable[[], Any],
        target_application: str = "",
        target_window: str = "",
        correlation_id: str = "",
    ) -> tuple:
        """One-shot canonical path: gate.evaluate → SafetyExecutor.execute.

        Returns ``(decision, envelope, result)``. Raises on ANY block.
        """
        gate = self._require_gate()
        decision = gate.evaluate(
            action,
            params,
            entry_point=entry_point,
            target_application=target_application,
            target_window=target_window,
            correlation_id=correlation_id,
        )
        envelope = build_envelope_from_decision(decision, params)
        result = self.execute(decision, envelope, runner)
        return decision, envelope, result


def build_envelope_from_decision(
    decision: SafetyDecision,
    params: Dict[str, Any],
) -> ActionEnvelope:
    """Rebuild the envelope matching a decision's recorded digest."""
    from .envelope import build_envelope

    env = build_envelope(
        action=decision.action,
        params=params,
        entry_point=decision.entry_point,
        target_application=decision.target_application,
        target_window=decision.target_window,
        zone=decision.zone,
        correlation_id="",  # binding digest excludes the volatile corr token
    )
    if decision.envelope_digest and env.digest() != decision.envelope_digest:
        raise SafetyExecutionBlocked(
            "envelope digest mismatch between caller payload and decision",
            decision,
        )
    return env


_DEFAULT_EXECUTOR: Optional[SafetyExecutor] = None


def get_executor(gate: Optional[SafetyDecisionGate] = None) -> SafetyExecutor:
    global _DEFAULT_EXECUTOR
    if gate is not None:
        return SafetyExecutor(gate)
    if _DEFAULT_EXECUTOR is None:
        _DEFAULT_EXECUTOR = SafetyExecutor()
    return _DEFAULT_EXECUTOR
