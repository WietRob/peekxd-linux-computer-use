"""Tests for semantic snapshot state-change detection."""

import pytest

from peekxd.semantic import (
    Geometry,
    SemanticElement,
    snapshot_diff,
    wait_for_state_change,
)


def _element(element_id, state, *, role="button", actions=None):
    return SemanticElement(
        element_id=element_id,
        raw_element_id=f"raw-{element_id}",
        window_id="W1",
        role=role,
        name=element_id,
        label=element_id,
        bbox=Geometry(x=0, y=0, width=10, height=10),
        state=state,
        actions=actions or ["click"],
        path=f"W1 > {role}[{element_id}]",
        confidence=0.9,
    )


def test_semantic_element_state_diff_reports_added_removed_and_changed_values():
    before = _element("W1-B1", {"enabled": True, "focused": False, "stale": "gone"})
    after = _element("W1-B1", {"enabled": False, "focused": False, "checked": True})

    assert before.state_diff(after) == {
        "changed": {"enabled": {"old": True, "new": False}},
        "added": {"checked": True},
        "removed": {"stale": "gone"},
    }


def test_snapshot_diff_reports_added_removed_and_state_changed_elements():
    before = [
        _element("W1-B1", {"enabled": True}),
        _element("W1-T1", {"focused": False}, role="text", actions=["focus", "type"]),
        _element("W1-M1", {"expanded": False}, role="menu"),
    ]
    after = [
        _element("W1-B1", {"enabled": False}),
        _element("W1-T1", {"focused": False}, role="text", actions=["focus", "type"]),
        _element("W1-L1", {"visited": False}, role="link"),
    ]

    assert snapshot_diff(before, after) == {
        "changed": {
            "W1-B1": {
                "changed": {"enabled": {"old": True, "new": False}},
                "added": {},
                "removed": {},
            }
        },
        "added": ["W1-L1"],
        "removed": ["W1-M1"],
        "unchanged": ["W1-T1"],
    }


def test_snapshot_diff_accepts_semantic_envelopes():
    before = {"snapshot": {"elements": [_element("W1-B1", {"enabled": True}).__dict__]}}
    after = {"snapshot": {"elements": [_element("W1-B1", {"enabled": False}).__dict__]}}

    diff = snapshot_diff(before, after)

    assert diff["changed"]["W1-B1"]["changed"] == {"enabled": {"old": True, "new": False}}


def test_wait_for_state_change_returns_element_when_expected_state_appears():
    snapshots = iter(
        [
            {"snapshot": {"elements": [_element("W1-B1", {"enabled": True}).__dict__]}},
            {"snapshot": {"elements": [_element("W1-B1", {"enabled": False}).__dict__]}},
        ]
    )

    element = wait_for_state_change(
        "W1-B1",
        {"enabled": False},
        timeout=1.0,
        poll_interval=0,
        snapshot_builder=lambda: next(snapshots),
    )

    assert element.element_id == "W1-B1"
    assert element.state["enabled"] is False


def test_wait_for_state_change_times_out_when_expected_state_never_appears():
    snapshot = {"snapshot": {"elements": [_element("W1-B1", {"enabled": True}).__dict__]}}

    with pytest.raises(TimeoutError, match="W1-B1.*enabled=False"):
        wait_for_state_change(
            "W1-B1",
            {"enabled": False},
            timeout=0,
            poll_interval=0,
            snapshot_builder=lambda: snapshot,
        )
