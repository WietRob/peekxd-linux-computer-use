"""Tests for the snapshot module scaffold."""

from peekxd.inspection.base import UIElement
from peekxd.snapshot import HybridDetector, SemanticElement, SnapshotStore


def test_snapshot_package_exports_scaffold_classes():
    assert SnapshotStore.__name__ == "SnapshotStore"
    assert SemanticElement.__name__ == "SemanticElement"
    assert HybridDetector.__name__ == "HybridDetector"


def test_snapshot_store_has_required_cache_methods():
    store = SnapshotStore()
    snapshot = {"snapshot_id": "snap-1", "elements": []}

    store.put("snap-1", snapshot)

    assert store.get("snap-1") == snapshot
    assert store.list() == ["snap-1"]
    assert store.delete("snap-1") is True
    assert store.get("snap-1") is None
    assert store.delete("snap-1") is False
    assert store.clean() == 0


def test_semantic_element_wraps_semantic_element_dict_with_typed_accessors():
    raw = {
        "element_id": "W1-B1",
        "raw_element_id": "raw-1",
        "window_id": "W1",
        "role": "push button",
        "name": "Save",
        "label": "Save file",
        "bbox": {"x": 10, "y": 20, "width": 80, "height": 30},
        "state": {"enabled": True},
        "actions": ["click"],
        "path": "W1 > push button[W1-B1]",
        "confidence": 0.95,
    }

    element = SemanticElement(raw)

    assert element.element_id == "W1-B1"
    assert element.raw_element_id == "raw-1"
    assert element.window_id == "W1"
    assert element.role == "push button"
    assert element.name == "Save"
    assert element.label == "Save file"
    assert element.bbox == {"x": 10, "y": 20, "width": 80, "height": 30}
    assert element.state == {"enabled": True}
    assert element.actions == ["click"]
    assert element.path == "W1 > push button[W1-B1]"
    assert element.confidence == 0.95
    assert element.to_dict() == raw


class _AvailableProvider:
    available = True

    def get_ui_tree(self, app_name=None):
        return [UIElement(id="raw-1", name="Save", role="push button", position=(0, 0), size=(1, 1))]


class _UnavailableProvider:
    available = False


class _VisionProvider:
    available = True


def test_hybrid_detector_prefers_available_atspi_provider():
    detector = HybridDetector(atspi_provider=_AvailableProvider(), vision_provider=_VisionProvider())

    assert isinstance(detector.detect(), _AvailableProvider)


def test_hybrid_detector_falls_back_to_available_vision_provider():
    detector = HybridDetector(atspi_provider=_UnavailableProvider(), vision_provider=_VisionProvider())

    assert isinstance(detector.detect(), _VisionProvider)
