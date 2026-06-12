"""Tests for removed WSL screenshot provider compatibility."""

import pytest

from peekxd.core.errors import ScreenshotError
from peekxd.screenshot.windows_wsl import WindowsWslProvider


def test_windows_wsl_provider_is_removed_stub(tmp_path):
    provider = WindowsWslProvider()
    assert provider.available is False
    assert provider.is_available() is False
    with pytest.raises(ScreenshotError, match="Visible screenshot capture is removed"):
        provider.capture_screen(str(tmp_path / "capture.png"))
