"""UI inspection module for peekxd Linux."""

from .base import UIElement, InspectionProvider
from .atspi import ATSPIProvider
from .detector import get_inspection_provider

__all__ = [
    "UIElement",
    "InspectionProvider",
    "ATSPIProvider",
    "get_inspection_provider",
]
