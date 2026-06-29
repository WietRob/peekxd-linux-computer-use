"""Typed wrapper around serialized semantic snapshot elements."""

from __future__ import annotations

from typing import Any, Dict, List


class SemanticElement:
    """Typed access wrapper for an existing ``peekxd.semantic`` element dict."""

    def __init__(self, raw: Dict[str, Any]) -> None:
        """Wrap a serialized semantic element mapping."""
        self._raw = dict(raw)

    @property
    def element_id(self) -> str:
        """Return the stable semantic element id."""
        return str(self._raw.get("element_id") or "")

    @property
    def raw_element_id(self) -> str:
        """Return the provider-native element id."""
        return str(self._raw.get("raw_element_id") or "")

    @property
    def window_id(self) -> str:
        """Return the semantic window id that owns this element."""
        return str(self._raw.get("window_id") or "")

    @property
    def role(self) -> str:
        """Return the accessible role name."""
        return str(self._raw.get("role") or "")

    @property
    def name(self) -> str:
        """Return the accessible name."""
        return str(self._raw.get("name") or "")

    @property
    def label(self) -> str:
        """Return the associated label text."""
        return str(self._raw.get("label") or "")

    @property
    def bbox(self) -> Dict[str, int]:
        """Return the serialized bounding box."""
        bbox = self._raw.get("bbox") or {}
        return {
            "x": int(bbox.get("x", 0) or 0),
            "y": int(bbox.get("y", 0) or 0),
            "width": int(bbox.get("width", 0) or 0),
            "height": int(bbox.get("height", 0) or 0),
        }

    @property
    def state(self) -> Dict[str, Any]:
        """Return the element state mapping."""
        return dict(self._raw.get("state") or {})

    @property
    def actions(self) -> List[str]:
        """Return action names advertised for this element."""
        return [str(action) for action in (self._raw.get("actions") or [])]

    @property
    def path(self) -> str:
        """Return the semantic path string."""
        return str(self._raw.get("path") or "")

    @property
    def confidence(self) -> float:
        """Return the confidence score for this element."""
        return float(self._raw.get("confidence", 0.0) or 0.0)

    def to_dict(self) -> Dict[str, Any]:
        """Return a shallow copy of the wrapped semantic element mapping."""
        return dict(self._raw)
