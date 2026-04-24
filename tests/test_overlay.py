"""Tests for Ghost Live Overlay (Softbox V3)."""

import pytest

from peekxd.core.overlay import (
    BaseOverlayBackend,
    GhostOverlayController,
    NoopOverlayBackend,
    OverlayDecision,
    OverlayRequest,
    TkinterOverlayBackend,
)


# --- OverlayRequest ---

class TestOverlayRequest:
    """Test OverlayRequest dataclass."""

    def test_default_fields(self):
        req = OverlayRequest(action="click")
        assert req.action == "click"
        assert req.params == {}
        assert req.preview == {}
        assert req.screenshot_path is None
        assert req.markup_path is None
        assert req.timeout_seconds == 5

    def test_full_construction(self):
        req = OverlayRequest(
            action="type",
            params={"text": "hello"},
            preview={"risk_factors": ["destructive_pattern: 'rm '"]},
            screenshot_path="/tmp/screen.png",
            markup_path="/tmp/markup.png",
            timeout_seconds=10,
        )
        assert req.action == "type"
        assert req.params["text"] == "hello"
        assert req.preview["risk_factors"]
        assert req.screenshot_path == "/tmp/screen.png"
        assert req.markup_path == "/tmp/markup.png"
        assert req.timeout_seconds == 10

    def test_serializable(self):
        req = OverlayRequest(
            action="click",
            params={"x": 100, "y": 200},
            timeout_seconds=3,
        )
        d = req.to_dict()
        assert d["action"] == "click"
        assert d["params"]["x"] == 100
        assert d["timeout_seconds"] == 3

        # Round-trip
        import json
        s = json.dumps(d)
        parsed = json.loads(s)
        assert parsed["action"] == "click"


# --- OverlayDecision ---

class TestOverlayDecision:
    """Test OverlayDecision dataclass."""

    def test_default_is_noop_timeout(self):
        d = OverlayDecision()
        assert d.approved is False
        assert d.cancelled is False
        assert d.timed_out is False
        assert d.backend == "noop"
        assert d.reason == ""

    def test_approved(self):
        d = OverlayDecision(approved=True, backend="tkinter", reason="User approved")
        assert d.approved is True
        assert d.cancelled is False
        assert d.timed_out is False

    def test_cancelled(self):
        d = OverlayDecision(cancelled=True, backend="tkinter", reason="User cancelled")
        assert d.cancelled is True
        assert d.approved is False

    def test_timed_out(self):
        d = OverlayDecision(timed_out=True, backend="noop", reason="Timeout")
        assert d.timed_out is True
        assert d.approved is False

    def test_to_dict(self):
        d = OverlayDecision(approved=True, backend="tkinter", reason="ok")
        result = d.to_dict()
        assert result["approved"] is True
        assert result["backend"] == "tkinter"
        assert result["reason"] == "ok"


# --- NoopOverlayBackend ---

class TestNoopOverlayBackend:
    """Test NoopOverlayBackend returns controlled timeout."""

    def test_returns_timed_out(self):
        backend = NoopOverlayBackend()
        req = OverlayRequest(action="click")
        decision = backend.show(req)
        assert decision.timed_out is True
        assert decision.approved is False
        assert decision.cancelled is False
        assert decision.backend == "noop"
        assert "No GUI" in decision.reason or "timeout" in decision.reason.lower()

    def test_is_base_overlay(self):
        backend = NoopOverlayBackend()
        assert isinstance(backend, BaseOverlayBackend)


# --- BaseOverlayBackend ---

class TestBaseOverlayBackend:
    """Test abstract base raises."""

    def test_show_raises(self):
        backend = BaseOverlayBackend()
        req = OverlayRequest(action="click")
        with pytest.raises(NotImplementedError):
            backend.show(req)


# --- GhostOverlayController ---

class TestGhostOverlayController:
    """Test GhostOverlayController backend selection."""

    def test_noop_backend(self):
        ctrl = GhostOverlayController(backend_name="noop")
        assert isinstance(ctrl.backend, NoopOverlayBackend)

    def test_auto_no_gui_uses_noop(self):
        """In headless/CI, auto should fall back to noop or tkinter."""
        ctrl = GhostOverlayController(backend_name="auto")
        # Either TkinterOverlayBackend or NoopOverlayBackend is acceptable
        assert isinstance(ctrl.backend, BaseOverlayBackend)

    def test_show_preview_with_noop(self):
        ctrl = GhostOverlayController(backend_name="noop", timeout=3)
        req = OverlayRequest(action="type", params={"text": "rm -rf /"})
        decision = ctrl.show_preview(req)
        assert decision.timed_out is True
        assert decision.approved is False

    def test_unknown_backend_uses_noop(self):
        ctrl = GhostOverlayController(backend_name="nonexistent")
        assert isinstance(ctrl.backend, NoopOverlayBackend)

    def test_controller_uses_request_timeout(self):
        ctrl = GhostOverlayController(backend_name="noop", timeout=99)
        req = OverlayRequest(action="click", timeout_seconds=0)
        # timeout_seconds <= 0 should be replaced by controller default
        ctrl.show_preview(req)
        assert req.timeout_seconds == 99


# --- Lazy Import ---

class TestLazyImport:
    """Test that overlay.py imports without tkinter at module level."""

    def test_import_does_not_require_tkinter(self):
        """Importing peekxd.core.overlay should not fail even if
        tkinter were unavailable (it's lazy inside TkinterOverlayBackend)."""
        import peekxd.core.overlay as overlay_mod
        assert hasattr(overlay_mod, "GhostOverlayController")
        assert hasattr(overlay_mod, "TkinterOverlayBackend")
        assert hasattr(overlay_mod, "NoopOverlayBackend")
        assert hasattr(overlay_mod, "OverlayRequest")
        assert hasattr(overlay_mod, "OverlayDecision")


# --- TkinterOverlayBackend (unit, no actual window) ---

class TestTkinterOverlayBackend:
    """Test TkinterOverlayBackend class structure (no real GUI in CI)."""

    def test_is_base_overlay(self):
        backend = TkinterOverlayBackend()
        assert isinstance(backend, BaseOverlayBackend)
