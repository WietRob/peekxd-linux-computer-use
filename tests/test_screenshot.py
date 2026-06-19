"""Tests for removed screenshot compatibility surface."""

import pytest

from peekxd.core.errors import ProviderNotAvailableError, ScreenshotError
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
def test_screenshot_providers_are_removed_stubs(provider_cls, tmp_path):
    provider = provider_cls()
    assert provider.is_available() is False
    with pytest.raises(ScreenshotError, match="Visible screenshot capture is removed"):
        provider.capture_screen(str(tmp_path / "out.png"))
    with pytest.raises(ScreenshotError, match="Visible screenshot capture is removed"):
        provider.capture_window(str(tmp_path / "out.png"))
    with pytest.raises(ScreenshotError, match="Visible screenshot capture is removed"):
        provider.capture_region(str(tmp_path / "out.png"), 1, 2, 3, 4)


def test_get_screenshot_provider_is_hard_disabled():
    with pytest.raises(ProviderNotAvailableError, match="Visible screenshot capture is removed"):
        get_screenshot_provider()


def test_base_contract_still_importable_for_compatibility():
    assert ScreenshotProvider is not None
