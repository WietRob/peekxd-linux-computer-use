"""Doctor checks for the REAL screenshot capability (G3 restoration)."""

import pytest

from peekxd.core.doctor import CapabilityStatus, run_doctor


def test_screenshot_capability_reports_provider_status():
    check = run_doctor(capability="screenshot").checks[0]
    # G3: capture is restored — the capability is never hard-"removed".
    assert check.provider != "removed"
    assert "removed" not in (check.evidence or {})
    assert check.status in (
        CapabilityStatus.OK,
        CapabilityStatus.BLOCKED,   # headless environments fail honestly
        CapabilityStatus.UNKNOWN,
    )


def test_screenshot_capability_smoke_reports_honestly(tmp_path):
    check = run_doctor(capability="screenshot", smoke=True, smoke_dir=tmp_path).checks[0]
    assert check.status in (CapabilityStatus.OK, CapabilityStatus.BLOCKED)
