"""Tests for semantic element action mapping helpers."""

from unittest.mock import MagicMock

import pytest

from peekxd.semantic import Geometry, SemanticElement, find_semantic_element


def _element(bbox):
    return SemanticElement(
        element_id="W1-B1",
        raw_element_id="raw-1",
        window_id="W1",
        role="button",
        name="OK",
        label="OK",
        bbox=bbox,
        state={"enabled": True},
        actions=["click"],
        path="W1 > button[W1-B1]",
        confidence=0.9,
    )


def test_click_center_maps_bbox_to_center_coordinates():
    element = _element(Geometry(x=20, y=10, width=50, height=30))
    input_provider = MagicMock()

    assert element.click_center(input_provider) == (45, 25)
    input_provider.click.assert_called_once_with(45, 25, "left")


def test_click_center_applies_hidpi_scale():
    element = _element(Geometry(x=10, y=20, width=30, height=30))
    input_provider = MagicMock()

    assert element.click_center(input_provider, scale=2.0) == (50, 70)
    input_provider.click.assert_called_once_with(50, 70, "left")


def test_type_into_clicks_zero_size_element_origin_before_typing():
    element = _element(Geometry(x=10, y=20, width=0, height=0))
    input_provider = MagicMock()

    assert element.type_into(input_provider, "hello") == (10, 20)
    input_provider.click.assert_called_once_with(10, 20, "left")
    input_provider.type_text.assert_called_once_with("hello")


def test_find_semantic_element_rehydrates_element_from_snapshot_dict():
    envelope = {
        "snapshot": {
            "elements": [
                {
                    "element_id": "W1-B1",
                    "raw_element_id": "raw-1",
                    "window_id": "W1",
                    "role": "button",
                    "name": "OK",
                    "label": "OK",
                    "bbox": {"x": 1, "y": 2, "width": 3, "height": 4},
                    "state": {"enabled": True},
                    "actions": ["click"],
                    "path": "W1 > button[W1-B1]",
                    "confidence": 0.9,
                }
            ]
        }
    }

    element = find_semantic_element(envelope, "W1-B1")

    assert element.bbox == Geometry(x=1, y=2, width=3, height=4)


def test_find_semantic_element_raises_for_missing_element_id():
    with pytest.raises(ValueError, match="semantic element not found: W1-B2"):
        find_semantic_element({"snapshot": {"elements": []}}, "W1-B2")