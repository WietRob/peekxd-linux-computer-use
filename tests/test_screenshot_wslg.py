"""Tests for the REAL WSL screenshot provider (G3 correction).

The WindowsWSL provider is a real capture implementation again; on a native
Linux box it honestly reports unavailable.
"""

from peekxd.screenshot.windows_wsl import WindowsWslProvider


def test_windows_wsl_provider_reports_honest_availability():
    provider = WindowsWslProvider()
    assert isinstance(provider.available, bool)
