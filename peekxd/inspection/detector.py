"""Inspection provider detector."""

from .base import InspectionProvider
from .atspi import ATSPIProvider
from ..core.errors import ProviderNotAvailableError


def get_inspection_provider() -> InspectionProvider:
    """Return the first available inspection provider.

    Currently checks, in order:
        1. :class:`ATSPIProvider` (AT-SPI2 via D-Bus).

    Returns:
        An instance of a concrete ``InspectionProvider``.

    Raises:
        ProviderNotAvailableError: If no provider can be used in the current
            environment.
    """
    providers = [ATSPIProvider()]
    for provider in providers:
        if provider.available:
            return provider
    raise ProviderNotAvailableError(
        "No inspection provider available. "
        "Install: python3-pyatspi2 and ensure at-spi2-registryd is running."
    )
