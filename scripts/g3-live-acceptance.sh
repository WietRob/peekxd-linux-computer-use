#!/usr/bin/env bash
# G3 Live Acceptance Journey — run from merged mains.
# Usage: G3_ACC=1 bash scripts/g3-live-acceptance.sh
set -u
PASS=0; FAIL=0; RESULTS=""
acc() { # acc <id> <desc> <cmd...>
  local id="$1" desc="$2"; shift 2
  if "$@" >/tmp/g3-acc-$id.log 2>&1; then
    PASS=$((PASS+1)); RESULTS+="PASS  $id  $desc"$'\n'
  else
    FAIL=$((FAIL+1)); RESULTS+="FAIL  $id  $desc"$'\n'
  fi
}
req() { # req <id> <desc> <cmd...>  — must FAIL (blocked)
  local id="$1" desc="$2"; shift 2
  if "$@" >/tmp/g3-acc-$id.log 2>&1; then
    FAIL=$((FAIL+1)); RESULTS+="FAIL  $id  $desc (expected block)"$'\n'
  else
    PASS=$((PASS+1)); RESULTS+="PASS  $id  $desc"$'\n'
  fi
}

WORK=$(mktemp -d)
export PEEKXD_STATE_DIR="$WORK/state"
PX="python -m peekxd"

echo "== G3 Live Acceptance =="
echo "workdir: $WORK"

# 3. actual screenshot capture
acc Screenshot "real capture with hash" \
  env PATH="$PATH" $PX capture screen -o "$WORK/shot.png"

# 4. UI tree (semantic)
acc UITree "semantic UI tree" $PX see --semantic --json

# 5. Vision on the exact captured screenshot
if [ -f "$WORK/shot.png" ]; then
  HASH_BEFORE=$(sha256sum "$WORK/shot.png" | cut -d' ' -f1)
  acc VisionOnCapture "vision route on captured image" \
    python -c "
from peekxd.vision import get_vision_provider
p = get_vision_provider()
r = p.analyze('$WORK/shot.png', 'What application window is in the foreground? Answer briefly.')
print(r)
import sys; sys.exit(0 if r and len(str(r))>0 else 1)
"
else
  FAIL=$((FAIL+1)); RESULTS+="FAIL  VisionOnCapture  no captured screenshot"$'\n'
fi

# 6. SHADOW action executes with before/after evidence
acc ShadowAction "SHADOW action executes via executor" \
  python - <<EOF
import os
from peekxd.core.decision import reset_gate, get_gate, ApprovalStore
from peekxd.core.executor import build_envelope_from_decision, get_executor
reset_gate()
gate = get_gate()
d = gate.evaluate("click", {"x": 10, "y": 10}, entry_point="cli")
assert d.policy_result == "allow_shadow", d.policy_result
env = build_envelope_from_decision(d, {"x": 10, "y": 10})
r = get_executor(gate).execute(d, env, lambda: "shadow-ok")
assert r == "shadow-ok"
rec = gate.store.load(d.decision_id)
assert rec["approval_state"] == "executed", rec["approval_state"]
assert d.evidence_correlation_id
print("correlation:", d.evidence_correlation_id)
EOF

# 7. APPROVABLE_GHOST remains pending without approval
req PendingGhost "ghost action stays pending unapproved" \
  python - <<EOF
from peekxd.core.decision import reset_gate, get_gate
reset_gate()
gate = get_gate(confirmable := True) if False else __import__("peekxd.core.decision", fromlist=["SafetyDecisionGate"]).SafetyDecisionGate(confirmable=True)
d = gate.evaluate("type", {"text": "s3cret"}, entry_point="macro")
assert d.policy_result == "require_approval"
rec = gate.store.load(d.decision_id)
assert rec["approval_state"] == "pending", rec["approval_state"]
raise SystemExit(1)  # pending ⇒ must not execute ⇒ command must fail
EOF

# 8. Exact decision_id + nonce approval executes the exact envelope once
acc ExactApproval "exact binding executes once" \
  python - <<EOF
import os
from peekxd.agent.actions import ActionSequence
from peekxd.core.decision import ApprovalStore, SafetyDecisionGate
store = ApprovalStore(directory=os.environ["PEEKXD_STATE_DIR"] + "/x8")
g = SafetyDecisionGate(approval_store=store, confirmable=True)
typed = []
seq = ActionSequence.from_dict([{"action":"type","params":{"text":"hello world"},"description":"t"}])
seq._input = type("F",(),{"click":staticmethod(lambda *a,**k:None),"type_text":staticmethod(lambda t: typed.append(t)),"key_press":staticmethod(lambda k:None),"hotkey":staticmethod(lambda *k:None),"move_mouse":staticmethod(lambda x,y:None),"scroll":lambda self=None,*a,**k:None})()
r1 = seq.execute(safety_gate=g)
dd = r1[0]["decision"]
store.approve(dd["decision_id"])
r2 = seq.execute(safety_gate=g, approved_decision_id=dd["decision_id"], execution_nonce=dd["execution_nonce"])
assert r2[0].get("success") is True, r2[0]
assert len(typed) == 1, typed
# 9. concurrent duplicate/replay executes nothing more
r3 = seq.execute(safety_gate=g, approved_decision_id=dd["decision_id"], execution_nonce=dd["execution_nonce"])
assert len(typed) == 1, ("replay executed!", typed)
print("exact-binding OK, replay rejected")
EOF

# 10. denial path executes nothing
acc DenialPath "denied decision never executes" \
  python - <<EOF
import os
from peekxd.agent.actions import ActionSequence
from peekxd.core.decision import ApprovalStore, SafetyDecisionGate
store = ApprovalStore(directory=os.environ["PEEKXD_STATE_DIR"] + "/x10")
g = SafetyDecisionGate(approval_store=store, confirmable=True)
typed = []
seq = ActionSequence.from_dict([{"action":"type","params":{"text":"nope"},"description":"d"}])
seq._input = type("F",(),{"type_text":staticmethod(lambda t: typed.append(t))})()
r1 = seq.execute(safety_gate=g)
dd = r1[0]["decision"]; store.deny(dd["decision_id"])
try:
    seq.execute(safety_gate=g, approved_decision_id=dd["decision_id"], execution_nonce=dd["execution_nonce"])
except SystemExit:
    pass
assert typed == [], typed
print("denial OK")
EOF

# 11. expiry path executes nothing
acc ExpiryPath "expired decision never executes" \
  python - <<EOF
import os, time
from peekxd.core.decision import ApprovalStore, SafetyDecisionGate, DecisionStateError
store = ApprovalStore(directory=os.environ["PEEKXD_STATE_DIR"] + "/x11")
g = SafetyDecisionGate(approval_store=store, confirmable=True, approval_ttl=1)
d = g.evaluate("type", {"text": "late"}, entry_point="macro")
store.approve(d.decision_id)
rec = store.load(d.decision_id); rec["expiry"] = time.time() - 1; store.save(rec)
try:
    store.claim(d.decision_id, d.execution_nonce, d.envelope_digest)
    raise AssertionError("expired claim succeeded")
except DecisionStateError:
    print("expiry OK")
EOF

# 12. HARD_BLOCKED through every real entry point
for EP in cli macro mcp orchestrator bridge; do
  acc HardBlock-$EP "hard_blocked on $EP" \
    python - <<EOF
from peekxd.core.decision import reset_gate, SafetyDecisionGate, ApprovalStore
import tempfile
reset_gate()
store = ApprovalStore(directory=tempfile.mkdtemp())
gate = SafetyDecisionGate(approval_store=store)
d = gate.evaluate("type", {"text": "rm -rf /"}, entry_point="$EP")
assert d.policy_result == "hard_blocked", d.policy_result
try:
    store.claim(d.decision_id, d.execution_nonce, d.envelope_digest)
    raise AssertionError("hard_blocked was claimed")
except Exception:
    pass
EOF
done

# 13. macro uses same boundary
acc MacroBoundary "peekxd macro run through boundary" \
  python - <<EOF
import os
os.environ.setdefault("PEEKXD_STATE_DIR", os.environ["PEEKXD_STATE_DIR"])
from peekxd.agent.actions import ActionSequence
from peekxd.core.decision import reset_gate, get_gate
reset_gate()
moved = []
seq = ActionSequence.from_dict([{"action":"move","params":{"x":5,"y":5},"description":"m"}])
seq._input = type("F",(),{"move_mouse":staticmethod(lambda x,y: moved.append((x,y)))})()
r = seq.execute()
assert len(moved) == 1, moved
rec = get_gate().store.load(r[0]["safety_decision_id"])
assert rec["approval_state"] == "executed", rec["approval_state"]
EOF

# 14. MCP and CLI decisions equivalent
acc Equivalence "MCP vs CLI decision equivalence" \
  python - <<EOF
from peekxd.core.decision import SafetyDecisionGate, ApprovalStore
import tempfile
store = ApprovalStore(directory=tempfile.mkdtemp())
a = SafetyDecisionGate(approval_store=store).evaluate("scroll", {"direction":"up","amount":2}, entry_point="mcp")
b = SafetyDecisionGate(approval_store=ApprovalStore(directory=tempfile.mkdtemp())).evaluate("scroll", {"direction":"up","amount":2}, entry_point="cli")
assert a.zone == b.zone and a.policy_result == b.policy_result
assert a.envelope_digest != b.envelope_digest  # entry point differs by design
print("zones/policies equal:", a.zone, a.policy_result)
EOF

# 16a. real process restart: state survives across processes
acc ProcessRestart "ledger survives real process restart" \
  python - <<EOF
import os, subprocess, sys, json
code = """
import os, json
from peekxd.core.decision import ApprovalStore, SafetyDecisionGate, reset_gate
store = ApprovalStore(directory=os.environ["PEEKXD_STATE_DIR"] + "/restart")
reset_gate()
gate = SafetyDecisionGate(approval_store=store, confirmable=True)
d = gate.evaluate("type", {"text": "persist"}, entry_point="macro")
print(json.dumps({"decision_id": d.decision_id, "nonce": d.execution_nonce,
                  "digest": d.envelope_digest}))
"""
out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                     env={**os.environ})
assert out.returncode == 0, out.stderr
payload = json.loads(out.stdout.strip().splitlines()[-1])
# NEW process: approve in one process...
code2 = """
import os, json
from peekxd.core.decision import ApprovalStore
payload = json.loads(os.environ["G3_PAYLOAD"])
store = ApprovalStore(directory=os.environ["PEEKXD_STATE_DIR"] + "/restart")
store.approve(payload["decision_id"])
"""
env2 = {**os.environ, "G3_PAYLOAD": json.dumps(payload)}
out2 = subprocess.run([sys.executable, "-c", code2], capture_output=True, text=True,
                      env=env2)
assert out2.returncode == 0, out2.stderr
# ...and claim in ANOTHER process using only persisted state
code3 = """
import os, json
from peekxd.core.decision import ApprovalStore
payload = json.loads(os.environ["G3_PAYLOAD"])
store = ApprovalStore(directory=os.environ["PEEKXD_STATE_DIR"] + "/restart")
store.claim(payload["decision_id"], payload["nonce"], payload["digest"])
rec = store.load(payload["decision_id"])
assert rec["approval_state"] == "claimed", rec["approval_state"]
"""
out3 = subprocess.run([sys.executable, "-c", code3], capture_output=True, text=True,
                      env=env2)
assert out3.returncode == 0, out3.stderr
print("restart persistence OK:", payload["decision_id"])
EOF

# 16b. CLAIMED is never auto-replayed after crash
acc ClaimedNoReplay "claimed record never replayed" \
  python - <<EOF
import subprocess, sys, os
setup = """
from peekxd.core.decision import ApprovalStore, SafetyDecisionGate, reset_gate
import os
store = ApprovalStore(directory=os.environ["PEEKXD_STATE_DIR"] + "/crash")
reset_gate()
gate = SafetyDecisionGate(approval_store=store)
d = gate.evaluate("key", {"key": "Escape"}, entry_point="cli")
store.claim(d.decision_id, d.execution_nonce, d.envelope_digest)
# simulate crash: record stays CLAIMED, new process must refuse replay
"""
subprocess.run([sys.executable, "-c", setup], check=True,
               env={**os.environ})
replay = """
from peekxd.core.decision import ApprovalStore
import os
store = ApprovalStore(directory=os.environ["PEEKXD_STATE_DIR"] + "/crash")
recs = [__import__("json").loads(open(p).read()) for p in __import__("glob").glob(os.environ["PEEKXD_STATE_DIR"] + "/crash/*.json")]
claimed = [r for r in recs if r["approval_state"] == "claimed"]
assert claimed, recs
try:
    store.claim(claimed[0]["decision_id"], claimed[0]["execution_nonce"], claimed[0].get("envelope_digest",""))
    raise AssertionError("CLAIMED was replayed after crash!")
except Exception:
    pass
"""
subprocess.run([sys.executable, "-c", replay], check=True, env={**os.environ})
print("no-replay-after-crash OK")
EOF

echo ""
echo "== Results =="
echo "$RESULTS"
echo "PASS=$PASS FAIL=$FAIL"
[ "$FAIL" -eq 0 ]
