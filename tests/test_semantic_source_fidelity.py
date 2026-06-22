"""Tests for dynamic semantic source fidelity metadata."""

from peekxd.inspection.base import UIElement
from peekxd.semantic import build_semantic_snapshot


class EmptyInspectionProvider:
    def get_ui_tree(self, app_name=None):
        return []


class PopulatedInspectionProvider:
    def get_ui_tree(self, app_name=None):
        return [
            UIElement(
                id="raw-1",
                name="Save",
                role="button",
                position=(10, 20),
                size=(30, 40),
                attributes={"enabled": True},
            )
        ]


class EmptyWindowProvider:
    def list_windows(self):
        return []


class WindowProvider:
    def list_windows(self):
        return [
            {
                "id": "native-1",
                "title": "Editor",
                "app_id": "editor",
                "x": 0,
                "y": 0,
                "width": 800,
                "height": 600,
                "focused": True,
            }
        ]


def test_empty_inspection_result_reports_low_fidelity_warning_and_missing_app():
    envelope = build_semantic_snapshot(
        app="firefox",
        inspection_provider=EmptyInspectionProvider(),
        window_provider=EmptyWindowProvider(),
    )

    source = envelope["snapshot"]["source"]

    assert source["source_fidelity"] == "low"
    assert source["completeness_score"] == 0.0
    assert source["missing_apps"] == ["firefox"]
    assert source["fallback_used"] is True
    assert source["warning"] == "live_accessibility_returned_no_elements"
    assert envelope["safety_state"]["code"] == "SEMANTIC_OK"


def test_populated_inspection_result_reports_high_fidelity_without_warning():
    envelope = build_semantic_snapshot(
        app="editor",
        inspection_provider=PopulatedInspectionProvider(),
        window_provider=WindowProvider(),
    )

    source = envelope["snapshot"]["source"]

    assert source["source_fidelity"] == "high"
    assert source["completeness_score"] == 1.0
    assert source["missing_apps"] == []
    assert source["fallback_used"] is False
    assert "warning" not in source
    assert envelope["safety_state"]["code"] == "SEMANTIC_OK"
