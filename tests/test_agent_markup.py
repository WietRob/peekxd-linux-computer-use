"""Tests for screen markup module."""

import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from peekxd.agent.screen_markup import draw_bounding_boxes


class TestDrawBoundingBoxes:
    """Test bounding box drawing."""

    def test_draw_boxes_with_pillow(self):
        """Test drawing bounding boxes on an image."""
        from PIL import Image

        # Create a test image
        img = Image.new("RGB", (800, 600), color="white")
        img_path = os.path.join(tempfile.gettempdir(), "test_markup_src.png")
        img.save(img_path)

        elements = [
            {"id": "0", "name": "Button", "role": "button", "position": (100, 100), "size": (80, 30)},
            {"id": "1", "name": "Input", "role": "textbox", "position": (200, 200), "size": (120, 25)},
        ]

        output_path = os.path.join(tempfile.gettempdir(), "test_markup_out.png")
        result = draw_bounding_boxes(img_path, elements, output_path)

        assert result == output_path
        assert os.path.exists(output_path)

    def test_empty_elements(self):
        """Test with no elements — just copies the image."""
        from PIL import Image

        img = Image.new("RGB", (100, 100), color="white")
        img_path = os.path.join(tempfile.gettempdir(), "test_empty_src.png")
        img.save(img_path)

        output_path = os.path.join(tempfile.gettempdir(), "test_empty_out.png")
        result = draw_bounding_boxes(img_path, [], output_path)

        assert result == output_path
        assert os.path.exists(output_path)


class TestAnalyzeScreenWithMarkup:
    """Test analyze_screen_with_markup function."""

    def test_analyze_parses_elements(self):
        """Test that AI response is parsed into elements."""
        from peekxd.agent.screen_markup import analyze_screen_with_markup

        mock_vision = MagicMock()
        mock_vision.analyze.return_value = (
            '[{"id": "0", "name": "OK Button", "role": "button", '
            '"position": {"x": 100, "y": 200}, "size": {"width": 60, "height": 30}}]'
        )

        from PIL import Image
        img = Image.new("RGB", (800, 600), color="white")
        img_path = os.path.join(tempfile.gettempdir(), "test_analyze_src.png")
        img.save(img_path)

        result = analyze_screen_with_markup(img_path, vision_provider=mock_vision)

        assert result["count"] == 1
        assert "0" in result["element_map"]
        assert result["elements"][0]["name"] == "OK Button"
        assert result["elements"][0]["position"] == (100, 200)
        assert result["elements"][0]["size"] == (60, 30)
        assert os.path.exists(result["markup_path"])

    def test_analyze_no_elements_found(self):
        """Test handling of empty response."""
        from peekxd.agent.screen_markup import analyze_screen_with_markup

        mock_vision = MagicMock()
        mock_vision.analyze.return_value = "[]"

        from PIL import Image
        img = Image.new("RGB", (800, 600), color="white")
        img_path = os.path.join(tempfile.gettempdir(), "test_empty2_src.png")
        img.save(img_path)

        result = analyze_screen_with_markup(img_path, vision_provider=mock_vision)

        assert result["count"] == 0
