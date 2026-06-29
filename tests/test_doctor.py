"""Tests for peekxd compatibility doctor."""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from peekxd.core.doctor import CapabilityStatus, run_doctor


def test_screenshot_capability_removed_even_when_tools_exist():
    with patch("peekxd.core.doctor.executable_available", return_value=True):
        check = run_doctor(capability="screenshot", smoke=True).checks[0]

    assert check.status == CapabilityStatus.BLOCKED
    assert check.provider == "removed"
    assert check.smoke_tested is False
    assert check.evidence["removed"] is True
    assert check.evidence["semantic_alternative"] == "peekxd see --semantic"
    assert "Visible screenshot capture is removed" in check.message


def test_screenshot_capability_removed_without_smoke():
    check = run_doctor(capability="screenshot", smoke=False).checks[0]

    assert check.status == CapabilityStatus.BLOCKED
    assert check.provider == "removed"
    assert check.smoke_tested is False
    assert "see --semantic" in check.fix_hint


def test_input_missing_blocked_without_crash():
    with patch("peekxd.core.doctor.get_input_provider", side_effect=RuntimeError("no input")), \
         patch("peekxd.core.doctor.executable_available", return_value=False):
        check = run_doctor(capability="input").checks[0]

    assert check.status == CapabilityStatus.BLOCKED
    assert check.capability == "input"
    assert "xdotool" in check.fix_hint


def test_input_doctor_reports_wtype_availability():
    with patch("peekxd.core.doctor.get_input_provider", return_value=SimpleNamespace(permission_label="wtype")), \
         patch("peekxd.core.doctor.executable_available", side_effect=lambda name: name == "wtype"):
        check = run_doctor(capability="input").checks[0]

    assert check.status == CapabilityStatus.OK
    assert check.evidence["tools"]["wtype"] is True
    assert check.evidence["tools"]["ydotool"] is False


def test_one_provider_exception_does_not_stop_all_checks():
    with patch("peekxd.core.doctor.get_input_provider", return_value=SimpleNamespace(permission_label="xdotool")):
        result = run_doctor(capabilities=["screenshot", "input"])

    statuses = {c.capability: c.status for c in result.checks}
    assert statuses["screenshot"] == CapabilityStatus.BLOCKED
    assert statuses["input"] == CapabilityStatus.OK


def test_json_serializable_and_no_private_smoke_path(tmp_path):
    payload = run_doctor(capability="screenshot", smoke=True, smoke_dir=tmp_path).to_dict()

    raw = json.dumps(payload)
    assert "checks" in payload
    assert str(Path.home()) not in raw
    assert str(tmp_path) not in raw
    assert "removed" in raw


def test_capability_filter_returns_only_requested_check():
    result = run_doctor(capability="desktop")
    assert [c.capability for c in result.checks] == ["desktop"]
