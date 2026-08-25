"""G3: canonical SafetyDecision boundary tests.

Every execution path must obtain exactly one SafetyDecision; denial,
timeout, replay and HARD_BLOCKED_GHOST must execute nothing.
"""

import tempfile
import time
from pathlib import Path

import pytest

from peekxd.core import decision as dec
from peekxd.core.decision import (
    ApprovalStore,
    DecisionStateError,
    SafetyDecisionGate,
)


@pytest.fixture()
def gate(tmp_path):
    store = ApprovalStore(directory=tmp_path / "approvals")
    return SafetyDecisionGate(approval_store=store, approval_ttl=120), store


def test_shadow_action_gets_allow_shadow_decision(gate):
    g, _ = gate
    d = g.evaluate("click", {"x": 10, "y": 20}, entry_point="macro")
    assert d.zone == "shadow"
    assert d.policy_result == "allow_shadow"
    assert d.decision_id and d.execution_nonce and d.evidence_correlation_id
    assert d.required_approval_state == "none"
    # decision persisted for correlation/restart proof
    assert g.store.load(d.decision_id) is not None


def test_destructive_type_is_hard_blocked_ghost(gate):
    g, _ = gate
    d = g.evaluate("type", {"text": "rm -rf /tmp/x"}, entry_point="macro")
    assert d.ghost_classification == "hard_blocked_ghost"
    assert d.policy_result == "hard_blocked"
    assert not g.is_execution_allowed(d)
    with pytest.raises(dec.DecisionDeniedError):
        raise dec.DecisionDeniedError(d)  # denial path raises, executes nothing


def test_credential_text_is_hard_blocked_per_v4_policy(gate):
    """Existing Softbox V4 policy: ANY risk factor -> HARD_BLOCKED_GHOST."""
    g, _ = gate
    d = g.evaluate("type", {"text": "my password is hunter2"}, entry_point="mcp")
    assert d.zone == "ghost"
    assert d.ghost_classification == "hard_blocked_ghost"
    assert d.policy_result == "hard_blocked"
    assert not g.is_execution_allowed(d)


def test_approve_then_consume_exactly_once(tmp_path):
    store = ApprovalStore(directory=tmp_path / "approvals")
    g = SafetyDecisionGate(approval_store=store, confirmable=True)
    d = g.evaluate("type", {"text": "hello world"}, entry_point="cli")
    assert d.policy_result == "require_approval"
    assert g.authorize(d) is True
    # replay of approve is rejected (already approved→consumed flow still one exec)
    rec = store.load(d.decision_id)
    assert rec["approval_state"] == "approved"
    assert g.consume(d) is True
    # replay of consume → rejected, executes nothing
    assert g.consume(d) is False
    with pytest.raises(DecisionStateError):
        store.approve(d.decision_id)


def test_denial_executes_nothing(gate):
    g, store = gate
    d = g.evaluate("type", {"text": "token value"}, entry_point="cli")
    assert g.deny(d) is True
    assert g.consume(d) is False  # denied decisions never execute
    assert store.load(d.decision_id)["approval_state"] == "denied"


def test_timeout_expiry_executes_nothing(tmp_path):
    """APPROVABLE_GHOST (confirmable) whose window lapses executes nothing."""
    store = ApprovalStore(directory=tmp_path / "approvals")
    g = SafetyDecisionGate(approval_store=store, approval_ttl=0,
                           confirmable=True)
    d = g.evaluate("click", {"x": 5, "y": 6}, entry_point="cli")
    assert d.policy_result == "require_approval"
    time.sleep(1.1)  # let the window lapse
    assert g.authorize(d) is False  # expired on approve
    assert g.consume(d) is False
    assert store.load(d.decision_id)["approval_state"] in ("expired", "pending")


def test_unknown_decision_rejected(tmp_path):
    store = ApprovalStore(directory=tmp_path / "approvals")
    with pytest.raises(DecisionStateError):
        store.approve("dec_does_not_exist")


def test_macro_run_bypass_closed():
    """The reported `peekxd macro run` bypass: destructive type must be
    blocked by the canonical boundary inside ActionSequence.execute."""
    from peekxd.agent.actions import ActionSequence

    seq = ActionSequence.from_dict([
        {"action": "type",
         "params": {"text": "rm -rf /tmp/peekxd-g3-test"},
         "description": "destructive probe"}])
    executed = []
    seq._input = type("FakeInput", (), {
        "click": staticmethod(lambda *a, **k: executed.append(("click", a))),
        "type_text": staticmethod(lambda t: executed.append(("type", t))),
        "key_press": staticmethod(lambda k: None),
        "hotkey": staticmethod(lambda *k: None),
        "move_mouse": staticmethod(lambda x, y: None),
        "scroll": lambda self=None, *a, **k: None,
    })()

    results = seq.execute(safety_gate=SafetyDecisionGate(
        approval_store=ApprovalStore(directory=Path(tempfile.mkdtemp()) / "approvals"),
    ))

    assert executed == [], "destructive action must NOT execute"
    r = results[0]
    assert r["success"] is False and r.get("blocked") is True
    assert r["decision"]["ghost_classification"] == "hard_blocked_ghost"


def test_macro_run_harmless_click_executes_with_correlation(tmp_path):
    from peekxd.agent.actions import ActionSequence

    seq = ActionSequence.from_dict([
        {"action": "click", "params": {"x": 1, "y": 2},
         "description": "harmless"}])
    executed = []
    seq._input = type("FakeInput", (), {
        "click": staticmethod(lambda x, y, button="left": executed.append((x, y))),
        "type_text": staticmethod(lambda t: None),
        "key_press": staticmethod(lambda k: None),
        "hotkey": staticmethod(lambda *k: None),
        "move_mouse": staticmethod(lambda x, y: None),
        "scroll": lambda self=None, *a, **k: None,
    })()
    store = ApprovalStore(directory=tmp_path / "approvals")
    g = SafetyDecisionGate(approval_store=store)
    results = seq.execute(safety_gate=g)

    assert len(executed) == 1
    r = results[0]
    assert r["success"] is True
    assert r["safety_policy"] == "allow_shadow"
    assert r["evidence_correlation_id"]
    # the decision is terminally EXECUTED in the ledger (atomic claim machine)
    rec = store.load(r["safety_decision_id"])
    assert rec["approval_state"] == "executed"


def test_pending_ghost_blocks_step_until_approved(tmp_path):
    from peekxd.agent.actions import ActionSequence

    seq = ActionSequence.from_dict([
        {"action": "type", "params": {"text": "hello world"},
         "description": "credential-ish"}])
    typed = []
    seq._input = type("FakeInput", (), {
        "click": staticmethod(lambda *a, **k: None),
        "type_text": staticmethod(lambda t: typed.append(t)),
        "key_press": staticmethod(lambda k: None),
        "hotkey": staticmethod(lambda *k: None),
        "move_mouse": staticmethod(lambda x, y: None),
        "scroll": lambda self=None, *a, **k: None,
    })()
    store = ApprovalStore(directory=tmp_path / "approvals")
    g = SafetyDecisionGate(approval_store=store, confirmable=True)

    results = seq.execute(safety_gate=g)
    assert typed == []  # nothing executed while pending
    assert results[0].get("pending_approval") is True

    # operator approves out-of-band via store, bound to the EXACT decision…
    d1 = results[0]["decision"]
    store.approve(d1["decision_id"])
    # …and a fresh sequence run redeems it via decision_id + nonce, exactly once:
    results2 = seq.execute(
        safety_gate=g,
        approved_decision_id=d1["decision_id"],
        execution_nonce=d1["execution_nonce"],
    )
    assert typed == ["hello world"], "approved action now executed once"
    assert results2[0]["success"] is True

    # replay with the same binding executes nothing more:
    results3 = seq.execute(
        safety_gate=g,
        approved_decision_id=d1["decision_id"],
        execution_nonce=d1["execution_nonce"],
    )
    assert len(typed) == 1, "replay must not execute again"
    assert results3[0].get("pending_approval") is True
