"""AT-SPI2 inspection provider for Linux accessibility APIs."""

import logging
import warnings
from typing import Any, Dict, List, Optional, Tuple

from .base import InspectionProvider, UIElement
from ..core.errors import InspectionError

logger = logging.getLogger(__name__)


class ATSPIProvider(InspectionProvider):
    """UI inspection provider using AT-SPI2 via D-Bus.

    This provider requires ``python3-pyatspi2`` to be installed and the
    ``at-spi2-registryd`` daemon to be running.  All ``pyatspi`` imports are
    deferred to method call time so that the class can be instantiated even
    when the library is not present.
    """

    @property
    def available(self) -> bool:
        """Return ``True`` if ``pyatspi`` can be imported."""
        try:
            import pyatspi  # noqa: F401
            return True
        except ImportError:
            return False

    def _get_registry(self) -> Any:
        """Return the pyatspi Registry (lazy import)."""
        import pyatspi
        return pyatspi.Registry

    def _build_element_id(self, *indices: int) -> str:
        """Create a unique element ID from integer indices."""
        return ":".join(str(i) for i in indices)

    def _traverse(self, accessible: Any, parent_id: Optional[str], ids: List[int]) -> List[UIElement]:
        """Recursively traverse accessible children and build UIElement list."""
        elements: List[UIElement] = []
        element_id = self._build_element_id(*ids)
        try:
            name = accessible.name or ""
            role = accessible.getRoleName() or "unknown"
            try:
                comp = accessible.queryComponent()
                extents = comp.getExtents(0)  # 0 = ATSPI_COORD_TYPE_SCREEN
                position = (int(extents.x), int(extents.y))
                size = (int(extents.width), int(extents.height))
            except Exception:
                position = (-1, -1)
                size = (-1, -1)
            try:
                child_count = accessible.childCount
            except Exception:
                child_count = 0
            children_ids: List[str] = []
            for i in range(child_count):
                child_id = self._build_element_id(*ids, i)
                children_ids.append(child_id)
                try:
                    child = accessible.getChildAtIndex(i)
                    elements.extend(self._traverse(child, element_id, [*ids, i]))
                except Exception as exc:
                    logger.debug("Skipping inaccessible child at %s:%d: %s", element_id, i, exc)
            element = UIElement(
                id=element_id,
                name=name,
                role=role,
                position=position,
                size=size,
                parent=parent_id,
                children=children_ids,
                attributes={"childCount": child_count},
            )
            elements.insert(0, element)
        except Exception as exc:
            logger.debug("Error traversing node %s: %s", element_id, exc)
        return elements

    def get_ui_tree(self, app_name: Optional[str] = None) -> List[UIElement]:
        """Return UI elements via AT-SPI2, optionally filtered by app name.

        Args:
            app_name: If given, only return elements from the application whose
                name contains this substring (case-insensitive).

        Returns:
            Flat list of ``UIElement`` instances.  Returns an empty list when
            the AT-SPI registry cannot be reached.
        """
        try:
            import pyatspi
            registry = pyatspi.Registry
            desktop = registry.getDesktop(0)
        except Exception as exc:
            warnings.warn(
                f"AT-SPI2 is not available or the registry is not running: {exc}",
                RuntimeWarning,
                stacklevel=2,
            )
            return []

        elements: List[UIElement] = []
        try:
            app_count = desktop.childCount
        except Exception as exc:
            logger.warning("Cannot query desktop children: %s", exc)
            return []

        for app_idx in range(app_count):
            try:
                app = desktop.getChildAtIndex(app_idx)
                app_name_actual = (app.name or "").lower()
                if app_name and app_name.lower() not in app_name_actual:
                    continue
                app_id = self._build_element_id(app_idx)
                try:
                    child_count = app.childCount
                except Exception:
                    child_count = 0
                children_ids: List[str] = []
                for child_idx in range(child_count):
                    child_id = self._build_element_id(app_idx, child_idx)
                    children_ids.append(child_id)
                    try:
                        child = app.getChildAtIndex(child_idx)
                        elements.extend(self._traverse(child, app_id, [app_idx, child_idx]))
                    except Exception as exc:
                        logger.debug("Skipping app child %d:%d: %s", app_idx, child_idx, exc)
                app_element = UIElement(
                    id=app_id,
                    name=app.name or "",
                    role="application",
                    position=(-1, -1),
                    size=(-1, -1),
                    parent=None,
                    children=children_ids,
                    attributes={"childCount": child_count},
                )
                elements.insert(0, app_element)
            except Exception as exc:
                logger.debug("Error processing app %d: %s", app_idx, exc)

        return elements

    def find_element(
        self,
        name: Optional[str] = None,
        role: Optional[str] = None,
        label: Optional[str] = None,
    ) -> Optional[UIElement]:
        """Search the UI tree for the first matching element.

        Matching is case-insensitive for *name* and *label*; *role* must match
        exactly (case-insensitive).
        """
        for element in self.get_ui_tree():
            if name is not None and name.lower() not in element.name.lower():
                continue
            if role is not None and role.lower() != element.role.lower():
                continue
            if label is not None:
                element_label = str(element.attributes.get("label", ""))
                if label.lower() not in element_label.lower():
                    continue
            return element
        return None

    def get_element_position(self, element_id: str) -> Tuple[int, int]:
        """Return the (x, y) screen coordinates of an element by its ID.

        Raises:
            InspectionError: If the element is not found in the current tree.
        """
        for element in self.get_ui_tree():
            if element.id == element_id:
                if element.position == (-1, -1):
                    raise InspectionError(
                        f"Element {element_id!r} does not have a valid position",
                        details={"element": element._asdict()},
                    )
                return element.position
        raise InspectionError(f"Element {element_id!r} not found in UI tree")

    def list_applications(self) -> List[Dict[str, Any]]:
        """Return a list of running accessible applications.

        Each dict contains ``name`` and ``id`` keys.  Returns an empty list
        when AT-SPI2 is unavailable.
        """
        apps: List[Dict[str, Any]] = []
        try:
            import pyatspi
            registry = pyatspi.Registry
            desktop = registry.getDesktop(0)
        except Exception as exc:
            warnings.warn(
                f"AT-SPI2 is not available or the registry is not running: {exc}",
                RuntimeWarning,
                stacklevel=2,
            )
            return apps

        try:
            count = desktop.childCount
        except Exception as exc:
            logger.warning("Cannot query desktop children: %s", exc)
            return apps

        for i in range(count):
            try:
                app = desktop.getChildAtIndex(i)
                apps.append({
                    "name": app.name or "",
                    "id": self._build_element_id(i),
                })
            except Exception as exc:
                logger.debug("Skipping app %d: %s", i, exc)
        return apps
