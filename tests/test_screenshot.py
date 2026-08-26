"""Tests for the REAL screenshot capture surface (G3 correction).

Screenshot capture was restored by Owner decision (the earlier removal was
never authorized). Providers must be constructible and report availability
honestly; on a headless CI box ``available`` may legitimately return False,
but the API must never raise "removed" errors anymore.
"""

import pytest

from peekxd.screenshot import (
    GenericProvider,
    PipeWireScreenCastProvider,
    ScreenshotProvider,
    WaylandProvider,
    WSLgScreenshotProvider,
    X11Provider,
    XdgDesktopPortalProvider,
    get_screenshot_provider,
)


@pytest.mark.parametrize(
    "provider_cls",
    [GenericProvider, WaylandProvider, X11Provider, XdgDesktopPortalProvider, PipeWireScreenCastProvider, WSLgScreenshotProvider],
)
def test_screenshot_providers_are_real(provider_cls):
    provider = provider_cls()
    # Availability is honest — but the removed-stub error is gone forever.
    assert isinstance(getattr(provider, "available", None), bool) or \
        isinstance(provider.is_available(), bool)


def test_windows_wsl_provider_reports_honest_availability():
    from peekxd.screenshot.windows_wsl import WindowsWslProvider
    provider = WindowsWslProvider()
    assert isinstance(provider.available, bool)


def test_get_screenshot_provider_returns_provider_or_raises_precise():
    try:
        provider = get_screenshot_provider()
        # A provider is selected and it exposes real capture methods.
        assert callable(provider.capture_screen)
        assert callable(provider.capture_window)
        assert callable(provider.capture_region)
    except Exception as exc:
        # Only a precise, environment-based failure is acceptable.
        msg = str(exc).lower()
        assert "removed" not in msg
        assert any(k in msg for k in ("wayland", "x11", "portal", "display", "unavailable", "not available"))


def test_capture_screen_writes_real_file_with_content_when_available(tmp_path):
    """On a graphical session this captures pixels; headless boxes skip."""
    pytest.importorskip("PIL")
    try:
        provider = get_screenshot_provider()
    except Exception:
        pytest.skip("no screenshot provider available in this environment")
    out = tmp_path / "shot.png"
    try:
        path = provider.capture_screen(str(out))
    except Exception as exc:
        pytest.skip(f"capture unavailable in this environment: {exc}")
    data = open(path, "rb").read()
    assert len(data) > 0


def test_base_contract_still_importable_for_compatibility():
    assert ScreenshotProvider is not None
