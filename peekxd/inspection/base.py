"""Base types and abstract class for UI inspection providers."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, NamedTuple, Optional, Tuple


class UIElement(NamedTuple):
    """Represents a UI element discovered via accessibility APIs.

    Attributes:
        id: Unique identifier string (format varies by provider).
        name: Accessible name of the element.
        role: Accessibility role (e.g. "button", "text", "frame").
        position: Screen coordinates (x, y) of the element.
        size: Dimensions (width, height) of the element.
        parent: ID of the parent element, if any.
        children: List of child element IDs.
        attributes: Additional provider-specific attributes.
    """

    id: str
    name: str
    role: str
    position: Tuple[int, int]
    size: Tuple[int, int]
    parent: Optional[str] = None
    children: List[str] = []
    attributes: Dict[str, Any] = {}


class InspectionProvider(ABC):
    """Abstract base class for UI inspection providers.

    Implementations use platform-specific accessibility APIs (e.g. AT-SPI2 on
    Linux) to enumerate UI elements and expose their properties.
    """

    @abstractmethod
    def get_ui_tree(self, app_name: Optional[str] = None) -> List[UIElement]:
        """Return the UI element tree, optionally filtered by application name.

        Args:
            app_name: If provided, only return elements from the matching app.

        Returns:
            A flat list of ``UIElement`` instances in tree order.
        """
        ...

    @abstractmethod
    def find_element(
        self,
        name: Optional[str] = None,
        role: Optional[str] = None,
        label: Optional[str] = None,
    ) -> Optional[UIElement]:
        """Search the UI tree for the first matching element.

        Args:
            name: Match the element's accessible name.
            role: Match the element's role.
            label: Match a label-related attribute.

        Returns:
            The first matching ``UIElement`` or ``None``.
        """
        ...

    @abstractmethod
    def get_element_position(self, element_id: str) -> Tuple[int, int]:
        """Return the (x, y) screen coordinates of an element by ID.

        Args:
            element_id: Unique identifier of the element.

        Returns:
            Tuple of (x, y) screen coordinates.

        Raises:
            InspectionError: If the element cannot be found.
        """
        ...

    @abstractmethod
    def list_applications(self) -> List[Dict[str, Any]]:
        """Return a list of running accessible applications.

        Returns:
            Each dict contains at least ``name`` and ``id`` keys.
        """
        ...

    @property
    @abstractmethod
    def available(self) -> bool:
        """Whether this provider can be used in the current environment."""
        ...
