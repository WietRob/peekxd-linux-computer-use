"""Tests for peekxd compatibility doctor."""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from PIL import Image

from peekxd.core.doctor import CapabilityStatus, run_doctor


def _png(path: Path, size=(8, 6)):
    Image.new("RGBA", size, (0, 0, 0, 255)).save(path)


def test_wslg_screenshot_ok_with_smoke(tmp_path):
    out = tmp_path / "smoke.png"
    _png(out, size=(16, 12))
    provider = MagicMock()
    provider.permission_label = "wslg/windows-host"
    provider.capture_screen.return_value = str(out)

    with patch("peekxd.core.doctor.get_screenshot_provider", return_value=provider), \
         patch("peekxd.core.doctor._safe_provider_label", return_value="wslg/windows-host"):
        result = run_doctor(capability="screenshot", smoke=True, smoke_dir=tmp_path)

    check = result.checks[0]
    assert check.status == CapabilityStatus.OK
    assert check.provider == "wslg/windows-host"
    assert check.smoke_tested is True
    assert check.evidence["dimensions"] == "16x12"
    assert check.evidence["mode"] == "RGBA"


def test_x11_import_fail_xwd_convert_fallback_reported_ok(tmp_path):
    out = tmp_path / "smoke.png"
    _png(out)
    provider = MagicMock()
    provider.__class__.__name__ = "X11Provider"
    provider.capture_screen.return_value = str(out)

    with patch("peekxd.core.doctor.get_screenshot_provider", return_value=provider), \
         patch("peekxd.core.doctor._safe_provider_label", return_value="X11Provider"), \
         patch("peekxd.core.doctor.executable_available", side_effect=lambda n: n in ("import", "xwd", "convert")):
        check = run_doctor(capability="screenshot", smoke=True, smoke_dir=tmp_path).checks[0]

    assert check.status == CapabilityStatus.OK
    assert check.provider == "X11Provider"
    assert check.evidence["tools"]["import"] is True
    assert check.evidence["tools"]["xwd"] is True
    assert check.evidence["tools"]["convert"] is True


def test_wayland_grim_fail_wayshot_fallback_reported_ok(tmp_path):
    out = tmp_path / "smoke.png"
    _png(out)
    provider = MagicMock()
    provider.__class__.__name__ = "WaylandProvider"
    provider.capture_screen.return_value = str(out)

    with patch("peekxd.core.doctor.get_screenshot_provider", return_value=provider), \
         patch("peekxd.core.doctor._safe_provider_label", return_value="WaylandProvider"), \
         patch("peekxd.core.doctor.executable_available", side_effect=lambda n: n in ("grim", "wayshot")):
        check = run_doctor(capability="screenshot", smoke=True, smoke_dir=tmp_path).checks[0]

    assert check.status == CapabilityStatus.OK
    assert check.provider == "WaylandProvider"
    assert check.evidence["tools"]["grim"] is True
    assert check.evidence["tools"]["wayshot"] is True


def test_missing_screenshot_providers_blocked_with_fix_hint():
    with patch("peekxd.core.doctor.get_screenshot_provider", side_effect=RuntimeError("none")), \
         patch("peekxd.core.doctor.executable_available", return_value=False):
        check = run_doctor(capability="screenshot").checks[0]

    assert check.status == CapabilityStatus.BLOCKED
    assert "Install" in check.fix_hint
    assert check.smoke_tested is False


def test_input_missing_blocked_without_crash():
    with patch("peekxd.core.doctor.get_input_provider", side_effect=RuntimeError("no input")), \
         patch("peekxd.core.doctor.executable_available", return_value=False):
        check = run_doctor(capability="input").checks[0]

    assert check.status == CapabilityStatus.BLOCKED
    assert check.capability == "input"
    assert "xdotool" in check.fix_hint


def test_one_provider_exception_does_not_stop_all_checks():
    with patch("peekxd.core.doctor.get_screenshot_provider", side_effect=RuntimeError("broken")), \
         patch("peekxd.core.doctor.get_input_provider", return_value=SimpleNamespace(permission_label="xdotool")):
        result = run_doctor(capabilities=["screenshot", "input"])

    statuses = {c.capability: c.status for c in result.checks}
    assert statuses["screenshot"] == CapabilityStatus.BLOCKED
    assert statuses["input"] == CapabilityStatus.OK


def test_json_serializable_and_no_private_smoke_path(tmp_path):
    out = tmp_path / "smoke.png"
    _png(out)
    provider = MagicMock()
    provider.capture_screen.return_value = str(out)

    with patch("peekxd.core.doctor.get_screenshot_provider", return_value=provider):
        payload = run_doctor(capability="screenshot", smoke=True, smoke_dir=tmp_path).to_dict()

    raw = json.dumps(payload)
    assert "checks" in payload
    assert str(Path.home()) not in raw
    assert str(tmp_path) not in raw
    assert "smoke.png" in raw


def test_capability_filter_returns_only_requested_check():
    result = run_doctor(capability="desktop")
    assert [c.capability for c in result.checks] == ["desktop"]
