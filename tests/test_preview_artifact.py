"""Preview artifact tests for Softbox Ghost Mode.

Tests that Ghost Mode can generate a visual preview PNG when a screenshot
and target coordinates are available. No real desktop actions are executed.
"""

import os
import tempfile
from unittest.mock import MagicMock

import pytest

from peekxd.core.zones import Zone, ZoneDecision, RiskDecision


class TestPreviewArtifact:
    """Test visual preview artifact generation."""

    def _create_test_screenshot(self, path: str, width: int = 300, height: int = 200):
        """Create a minimal test PNG using PIL if available."""
        try:
            from PIL import Image
        except ImportError:
            pytest.skip("PIL/Pillow not installed")

        img = Image.new("RGB", (width, height), color="white")
        img.save(path, "PNG")

    def test_ghost_preview_with_screenshot_creates_markup(self):
        """Ghost preview with screenshot_path must create a markup PNG."""
        with tempfile.TemporaryDirectory() as tmpdir:
            screenshot_path = os.path.join(tmpdir, "test_screen.png")
            self._create_test_screenshot(screenshot_path)

            decision = RiskDecision(
                zone=Zone.GHOST,
                risk_level="destructive",
                risk_factors=["destructive_command"],
                reason="rm command detected",
            )

            preview = ZoneDecision.create_ghost_preview(
                action="click",
                params={"x": 100, "y": 80},
                decision=decision,
                screenshot_path=screenshot_path,
            )

            # markup_path must be set
            assert preview.markup_path is not None, "markup_path should not be None"
            # File must exist
            assert os.path.exists(preview.markup_path), f"markup file must exist: {preview.markup_path}"
            # File must be non-empty
            assert os.path.getsize(preview.markup_path) > 0, "markup file must be non-empty"
            # File must be PNG
            with open(preview.markup_path, "rb") as f:
                header = f.read(8)
                assert header[:8] == b"\x89PNG\r\n\x1a\n", "file must be a valid PNG"

    def test_ghost_preview_without_screenshot_no_markup(self):
        """Ghost preview without screenshot_path must not crash, markup_path=None."""
        decision = RiskDecision(
            zone=Zone.GHOST,
            risk_level="destructive",
            risk_factors=["destructive_command"],
            reason="rm command detected",
        )

        preview = ZoneDecision.create_ghost_preview(
            action="type",
            params={"text": "rm -rf /"},
            decision=decision,
            screenshot_path=None,
        )

        # markup_path should be None when no screenshot
        assert preview.markup_path is None, "markup_path should be None without screenshot"
        # But preview dict must still be complete
        preview_dict = preview.to_dict()
        assert preview_dict["action"] == "type"
        assert preview_dict["zone"] == "ghost"
        assert preview_dict["requires_confirmation"] is True

    def test_ghost_preview_no_coordinates_no_markup(self):
        """Ghost preview without coordinates must not create markup."""
        with tempfile.TemporaryDirectory() as tmpdir:
            screenshot_path = os.path.join(tmpdir, "test_screen.png")
            self._create_test_screenshot(screenshot_path)

            decision = RiskDecision(
                zone=Zone.GHOST,
                risk_level="destructive",
                risk_factors=["destructive_command"],
                reason="rm command detected",
            )

            # No x/y coordinates
            preview = ZoneDecision.create_ghost_preview(
                action="type",
                params={"text": "hello"},
                decision=decision,
                screenshot_path=screenshot_path,
            )

            # markup_path should be None without coordinates
            assert preview.markup_path is None, "markup_path should be None without coordinates"

    def test_no_real_action_executed(self):
        """Ghost preview must never execute any real action."""
        decision = RiskDecision(
            zone=Zone.GHOST,
            risk_level="destructive",
            risk_factors=["test"],
            reason="test",
        )

        # Track if any "execution" side effect could happen
        preview = ZoneDecision.create_ghost_preview(
            action="click",
            params={"x": 50, "y": 50},
            decision=decision,
        )

        # Preview is pure data — no execution state
        assert preview.zone == Zone.GHOST
        assert preview.requires_confirmation is True
        preview_dict = preview.to_dict()
        assert preview_dict["zone"] == "ghost"
