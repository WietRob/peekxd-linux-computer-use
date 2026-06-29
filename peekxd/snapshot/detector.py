"""Hybrid detector scaffold for accessibility-first element detection."""

from __future__ import annotations

from typing import Any, Optional

from peekxd.core.errors import ProviderNotAvailableError
from peekxd.inspection.atspi import ATSPIProvider


class HybridDetector:
    """Select an AT-SPI provider first, then an optional vision provider fallback."""

    def __init__(self, atspi_provider: Optional[Any] = None, vision_provider: Optional[Any] = None) -> None:
        """Create a detector with optional injectable providers for tests."""
        self.atspi_provider = atspi_provider if atspi_provider is not None else ATSPIProvider()
        self.vision_provider = vision_provider

    def detect(self) -> Any:
        """Return the first available detector provider.

        The initial scaffold establishes the selection contract only: prefer
        AT-SPI for semantic fidelity, then use a provided vision provider when
        accessibility is unavailable.
        """
        if getattr(self.atspi_provider, "available", False):
            return self.atspi_provider
        if self.vision_provider is not None and getattr(self.vision_provider, "available", False):
            return self.vision_provider
        raise ProviderNotAvailableError("No snapshot detector provider available.")
