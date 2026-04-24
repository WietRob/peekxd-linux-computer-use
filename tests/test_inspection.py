"""Tests for the UI inspection module."""

import sys
import types
import warnings
from typing import Generator
from unittest.mock import MagicMock, patch

import pytest

from peekxd.inspection import (
    ATSPIProvider,
    UIElement,
    get_inspection_provider,
)
from peekxd.inspection.base import InspectionProvider
from peekxd.core.errors import InspectionError, ProviderNotAvailableError


# ---------------------------------------------------------------------------
# UIElement tests
# ---------------------------------------------------------------------------

class TestUIElement:
    """Tests for the ``UIElement`` named tuple."""

    def test_create_with_required_fields(self):
        el = UIElement(id="0:1", name="OK", role="button", position=(10, 20), size=(80, 30))
        assert el.id == "0:1"
        assert el.name == "OK"
        assert el.role == "button"
        assert el.position == (10, 20)
        assert el.size == (80, 30)
        assert el.parent is None
        assert el.children == []
        assert el.attributes == {}

    def test_create_with_all_fields(self):
        el = UIElement(
            id="0:1:2",
            name="Cancel",
            role="push button",
            position=(100, 200),
            size=(50, 25),
            parent="0:1",
            children=["0:1:2:0"],
            attributes={"label": "Cancel"},
        )
        assert el.parent == "0:1"
        assert el.children == ["0:1:2:0"]
        assert el.attributes == {"label": "Cancel"}

    def test_immutability(self):
        el = UIElement(id="0", name="app", role="application", position=(0, 0), size=(0, 0))
        with pytest.raises(AttributeError):
            el.name = "changed"  # type: ignore[misc]

    def test_defaults(self):
        el = UIElement(id="x", name="x", role="x", position=(0, 0), size=(0, 0))
        assert el.parent is None
        assert el.children == []
        assert el.attributes == {}


# ---------------------------------------------------------------------------
# InspectionProvider interface tests
# ---------------------------------------------------------------------------

class TestInspectionProviderInterface:
    """Tests ensuring concrete providers implement the required interface."""

    def test_atspi_provider_is_subclass(self):
        assert issubclass(ATSPIProvider, InspectionProvider)

    def test_abstract_methods(self):
        # Verify abstract methods exist on the interface
        for method_name in ("get_ui_tree", "find_element", "get_element_position", "list_applications"):
            assert hasattr(InspectionProvider, method_name)
        assert hasattr(InspectionProvider, "available")


# ---------------------------------------------------------------------------
# ATSPIProvider availability tests (mocked import)
# ---------------------------------------------------------------------------

class TestATSPIProviderAvailability:
    """Tests for the ``available`` property with mocked ``pyatspi``."""

    def test_available_when_pyatspi_imports(self):
        """available=True when pyatspi can be imported."""
        fake_mod = types.ModuleType("pyatspi")
        fake_mod.Registry = MagicMock()
        with patch.dict(sys.modules, {"pyatspi": fake_mod}):
            provider = ATSPIProvider()
            assert provider.available is True

    def test_not_available_when_pyatspi_missing(self):
        """available=False when pyatspi cannot be imported."""
        with patch.dict(sys.modules, {"pyatspi": None}):
            # patch.dict with None removes the key, simulating missing import
            provider = ATSPIProvider()
            # Force __import__ to raise ImportError for pyatspi
            real_import = __builtins__["__import__"] if isinstance(__builtins__, dict) else __builtins__.__import__

            def raising_import(name, *args, **kwargs):
                if name == "pyatspi":
                    raise ImportError("No module named pyatspi")
                return real_import(name, *args, **kwargs)

            with patch.dict(__builtins__, {"__import__": raising_import}):
                assert provider.available is False


# ---------------------------------------------------------------------------
# Lazy import tests
# ---------------------------------------------------------------------------

class TestLazyImport:
    """Verify pyatspi is not imported at module load time."""

    def test_pyatspi_not_in_sys_modules_after_import(self):
        """Importing the inspection module must not load pyatspi."""
        # Remove pyatspi from sys.modules if present
        mod_name = "pyatspi"
        had_it = mod_name in sys.modules
        saved = sys.modules.pop(mod_name, None)
        try:
            # The module should already be loaded; verify it didn't pull pyatspi
            assert mod_name not in sys.modules, (
                "pyatspi was loaded into sys.modules by importing peekxd.inspection"
            )
        finally:
            if had_it and saved is not None:
                sys.modules[mod_name] = saved


# ---------------------------------------------------------------------------
# get_inspection_provider tests
# ---------------------------------------------------------------------------

class TestGetInspectionProvider:
    """Tests for :func:`get_inspection_provider`."""

    def test_returns_atspi_when_available(self):
        with patch.object(ATSPIProvider, "available", new=True):
            provider = get_inspection_provider()
            assert isinstance(provider, ATSPIProvider)

    def test_raises_when_no_provider_available(self):
        with patch.object(ATSPIProvider, "available", new=False):
            with pytest.raises(ProviderNotAvailableError) as exc_info:
                get_inspection_provider()
            assert "python3-pyatspi2" in str(exc_info.value)


# ---------------------------------------------------------------------------
# ATSPIProvider method tests (with mocked pyatspi)
# ---------------------------------------------------------------------------

class TestATSPIProviderWithMock:
    """Tests for provider methods using a fully mocked pyatspi layer."""

    @pytest.fixture
    def mock_desktop(self) -> Generator[MagicMock, None, None]:
        """Provide a fake pyatspi Registry + desktop tree."""
        fake_mod = types.ModuleType("pyatspi")
        fake_registry = MagicMock()
        fake_desktop = MagicMock()
        fake_desktop.childCount = 1

        # Fake application
        fake_app = MagicMock()
        fake_app.name = "TestApp"
        fake_app.childCount = 1
        fake_app.getRoleName.return_value = "application"

        # Fake window (child of app)
        fake_window = MagicMock()
        fake_window.name = "Main Window"
        fake_window.getRoleName.return_value = "frame"
        fake_window.childCount = 1

        # Fake button (child of window)
        fake_button = MagicMock()
        fake_button.name = "Click Me"
        fake_button.getRoleName.return_value = "push button"
        fake_button.childCount = 0

        # Component interface for extents
        fake_comp = MagicMock()
        fake_extents = MagicMock(x=10, y=20, width=80, height=30)
        fake_comp.getExtents.return_value = fake_extents
        fake_button.queryComponent.return_value = fake_comp
        fake_window.queryComponent.return_value = fake_comp
        fake_app.queryComponent.return_value = fake_comp

        fake_window.getChildAtIndex.return_value = fake_button
        fake_app.getChildAtIndex.return_value = fake_window
        fake_desktop.getChildAtIndex.return_value = fake_app

        fake_registry.getDesktop.return_value = fake_desktop
        fake_mod.Registry = fake_registry

        with patch.dict(sys.modules, {"pyatspi": fake_mod}):
            yield fake_desktop

    def test_list_applications(self, mock_desktop):
        provider = ATSPIProvider()
        apps = provider.list_applications()
        assert len(apps) == 1
        assert apps[0]["name"] == "TestApp"

    def test_get_ui_tree_returns_elements(self, mock_desktop):
        provider = ATSPIProvider()
        elements = provider.get_ui_tree()
        assert len(elements) > 0
        roles = {el.role for el in elements}
        assert "application" in roles
        assert "frame" in roles
        assert "push button" in roles

    def test_get_ui_tree_filtered_by_app_name(self, mock_desktop):
        provider = ATSPIProvider()
        elements = provider.get_ui_tree(app_name="NonExistent")
        assert len(elements) == 0

    def test_find_element_by_name(self, mock_desktop):
        provider = ATSPIProvider()
        result = provider.find_element(name="Click Me")
        assert result is not None
        assert result.role == "push button"

    def test_find_element_by_role(self, mock_desktop):
        provider = ATSPIProvider()
        result = provider.find_element(role="frame")
        assert result is not None
        assert result.name == "Main Window"

    def test_find_element_no_match(self, mock_desktop):
        provider = ATSPIProvider()
        result = provider.find_element(name="Does Not Exist")
        assert result is None

    def test_get_element_position(self, mock_desktop):
        provider = ATSPIProvider()
        elements = provider.get_ui_tree()
        # Find the button element by role
        button = next(el for el in elements if el.role == "push button")
        pos = provider.get_element_position(button.id)
        assert pos == (10, 20)

    def test_get_element_position_not_found(self, mock_desktop):
        provider = ATSPIProvider()
        with pytest.raises(InspectionError) as exc_info:
            provider.get_element_position("999:999")
        assert "not found" in str(exc_info.value).lower()

    def test_graceful_on_dbus_error(self):
        """When getDesktop raises, get_ui_tree returns empty list with warning."""
        fake_mod = types.ModuleType("pyatspi")
        fake_registry = MagicMock()
        fake_registry.getDesktop.side_effect = RuntimeError("D-Bus error")
        fake_mod.Registry = fake_registry

        with patch.dict(sys.modules, {"pyatspi": fake_mod}):
            provider = ATSPIProvider()
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                result = provider.get_ui_tree()
                assert result == []
                assert len(w) == 1
                assert issubclass(w[0].category, RuntimeWarning)
                assert "D-Bus error" in str(w[0].message)


# ---------------------------------------------------------------------------
# Package init exports
# ---------------------------------------------------------------------------

class TestInspectionExports:
    """Smoke tests for the inspection package ``__init__``."""

    def test_can_import_all_symbols(self):
        from peekxd.inspection import (
            ATSPIProvider,
            InspectionProvider,
            UIElement,
            get_inspection_provider,
        )
        assert ATSPIProvider is not None
        assert InspectionProvider is not None
        assert UIElement is not None
        assert get_inspection_provider is not None
