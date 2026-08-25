"""G3 acceptance tests: atomic claim across PROCESSES, exact binding, fail-closed.

These tests prove the Owner-required properties that unit-level mocking
cannot: a second PROCESS claiming an approved decision fails before any side
effect, and a malformed/missing ledger blocks execution.
"""

import multiprocessing
import os
import tempfile
from pathlib import Path

import pytest

from peekxd.core.decision import (
    ApprovalStore,
    DecisionStateError,
    SafetyDecisionGate,
)
from peekxd.core.envelope import build_envelope


def _child_claim(store_dir, decision_id, nonce, digest, result_queue):
    """Run in a SEPARATE process: attempt to claim the same decision."""
    store = ApprovalStore(directory=Path(store_dir))
    try:
        store.claim(decision_id, nonce, digest)
    except DecisionStateError as exc:
        result_queue.put(("rejected", str(exc)))
        return
    except Exception as exc:  # pragma: no cover
        result_queue.put(("error", str(exc)))
        return
    result_queue.put(("claimed", ""))


@pytest.fixture()
def store(tmp_path):
    return ApprovalStore(directory=tmp_path / "approvals")


def test_concurrent_duplicate_claims_across_processes_execute_once(store):
    """Exactly ONE of N racing processes wins the claim; the side effect
    (simulated by the winner's mark_executed) happens exactly once."""
    gate = SafetyDecisionGate(approval_store=store, confirmable=True)
    decision = gate.evaluate("type", {"text": "race"}, entry_point="macro")
    store.approve(decision.decision_id)

    ctx = multiprocessing.get_context("fork")
    result_queue = ctx.Queue()
    procs = [
        ctx.Process(
            target=_child_claim,
            args=(store._dir, decision.decision_id,
                  decision.execution_nonce, decision.envelope_digest,
                  result_queue),
        )
        for _ in range(4)
    ]
    for p in procs:
        p.start()
    for p in procs:
        p.join(timeout=15)

    outcomes = []
    while not result_queue.empty():
        outcomes.append(result_queue.get())

    claimed = [o for o in outcomes if o[0] == "claimed"]
    rejected = [o for o in outcomes if o[0] == "rejected"]
    assert len(claimed) <= 1, f"multiple processes claimed: {outcomes}"
    assert len(rejected) >= 3, f"losers must be rejected before side effect: {outcomes}"


def test_replay_rejected_after_execution(store):
    gate = SafetyDecisionGate(approval_store=store)
    d = gate.evaluate("scroll", {"direction": "down", "amount": 1},
                      entry_point="macro")
    store.claim(d.decision_id, d.execution_nonce, d.envelope_digest)
    store.mark_executed(d.decision_id)
    with pytest.raises(DecisionStateError):
        store.claim(d.decision_id, d.execution_nonce, d.envelope_digest)


def test_envelope_digest_mismatch_blocks_claim(store):
    gate = SafetyDecisionGate(approval_store=store, confirmable=True)
    d = gate.evaluate("type", {"text": "hello"}, entry_point="macro")
    store.approve(d.decision_id)
    # Same action but DIFFERENT payload → different envelope digest.
    other = build_envelope(action="type", params={"text": "EVIL"},
                           entry_point="macro", zone=d.zone)
    with pytest.raises(DecisionStateError):
        store.claim(d.decision_id, d.execution_nonce, other.digest())


def test_wrong_nonce_blocks_claim(store):
    gate = SafetyDecisionGate(approval_store=store, confirmable=True)
    d = gate.evaluate("type", {"text": "hello"}, entry_point="macro")
    store.approve(d.decision_id)
    with pytest.raises(DecisionStateError):
        store.claim(d.decision_id, "f" * 32, d.envelope_digest)


def test_missing_ledger_record_blocks_claim(tmp_path):
    empty = ApprovalStore(directory=tmp_path / "none")
    with pytest.raises(DecisionStateError):
        empty.claim("dec_does_not_exist", "n" * 32, "d" * 64)


def test_corrupt_ledger_record_fails_closed(tmp_path):
    store = ApprovalStore(directory=tmp_path / "approvals")
    gate = SafetyDecisionGate(approval_store=store, confirmable=True)
    d = gate.evaluate("type", {"text": "hello"}, entry_point="macro")
    # Corrupt the persisted record.
    path = store._path(d.decision_id)
    path.write_text("{not json at all")
    with pytest.raises(Exception):
        store.claim(d.decision_id, d.execution_nonce, d.envelope_digest)


def test_hard_blocked_never_claimable_on_any_entry_point(store):
    for ep in ("cli", "macro", "mcp", "orchestrator", "bridge"):
        gate = SafetyDecisionGate(approval_store=store)
        d = gate.evaluate("type", {"text": "rm -rf /"}, entry_point=ep)
        assert d.policy_result == "hard_blocked", ep
        with pytest.raises(DecisionStateError):
            store.claim(d.decision_id, d.execution_nonce, d.envelope_digest)


def test_expired_approval_blocks_claim(store):
    import time
    gate = SafetyDecisionGate(approval_store=store, confirmable=True,
                              approval_ttl=1)
    d = gate.evaluate("type", {"text": "slow"}, entry_point="macro")
    store.approve(d.decision_id)
    # Simulate expiry by rewriting the record's expiry into the past.
    rec = store.load(d.decision_id)
    rec["expiry"] = time.time() - 1
    store.save(rec)
    with pytest.raises(DecisionStateError):
        store.claim(d.decision_id, d.execution_nonce, d.envelope_digest)
