"""Semantic snapshot model for ``peekxd see --semantic``.

This module intentionally depends only on accessibility/window providers. It
must not import screenshot, vision, PipeWire, portal, or visual-capture modules.
"""

from __future__ import annotations

import secrets
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

SCHEMA_VERSION = "peekxd.see.v1"


@dataclass(frozen=True)
class Geometry:
    x: int
    y: int
    width: int
    height: int

    def center(self, *, scale: float = 1.0) -> Tuple[int, int]:
        """Return the scaled center point for this rectangle.

        Zero-width or zero-height accessibility bounds intentionally map to the
        element origin. Some providers report caret/text nodes this way, and the
        origin remains the only actionable coordinate available.
        """
        if scale <= 0:
            raise ValueError("scale must be greater than zero")
        center_x = self.x if self.width <= 0 else self.x + (self.width / 2)
        center_y = self.y if self.height <= 0 else self.y + (self.height / 2)
        return int(round(center_x * scale)), int(round(center_y * scale))


@dataclass(frozen=True)
class SemanticWindow:
    window_id: str
    app_id: Optional[str]
    title: str
    is_focused: bool
    geometry: Geometry
    raw_window_id: Optional[str] = None


@dataclass(frozen=True)
class SemanticElement:
    element_id: str
    raw_element_id: str
    window_id: str
    role: str
    name: str
    label: str
    bbox: Geometry
    state: Dict[str, Any]
    actions: List[str]
    path: str
    confidence: float

    def click_center(self, input_provider: Any, *, button: str = "left", scale: float = 1.0) -> Tuple[int, int]:
        """Click this element's bounding-box center and return the coordinates used."""
        x, y = self.bbox.center(scale=scale)
        input_provider.click(x, y, button)
        return x, y

    def type_into(self, input_provider: Any, text: str, *, button: str = "left", scale: float = 1.0) -> Tuple[int, int]:
        """Focus this element by center-clicking it, then type text into it."""
        x, y = self.click_center(input_provider, button=button, scale=scale)
        input_provider.type_text(text)
        return x, y

    def state_diff(self, other: "SemanticElement") -> Dict[str, Dict[str, Any]]:
        """Return state keys added, removed, or changed between two elements."""
        before = dict(self.state or {})
        after = dict(other.state or {})
        changed = {
            key: {"old": before[key], "new": after[key]}
            for key in sorted(before.keys() & after.keys())
            if before[key] != after[key]
        }
        added = {key: after[key] for key in sorted(after.keys() - before.keys())}
        removed = {key: before[key] for key in sorted(before.keys() - after.keys())}
        return {"changed": changed, "added": added, "removed": removed}


def _geometry_from_mapping(raw: Any) -> Geometry:
    if isinstance(raw, Geometry):
        return raw
    return Geometry(
        x=int(raw.get("x", 0) or 0),
        y=int(raw.get("y", 0) or 0),
        width=int(raw.get("width", 0) or 0),
        height=int(raw.get("height", 0) or 0),
    )


def semantic_element_from_mapping(raw: Dict[str, Any]) -> SemanticElement:
    """Rehydrate a ``SemanticElement`` from a snapshot element dictionary."""
    bbox = raw.get("bbox", {}) or {}
    return SemanticElement(
        element_id=str(raw.get("element_id") or ""),
        raw_element_id=str(raw.get("raw_element_id") or ""),
        window_id=str(raw.get("window_id") or ""),
        role=str(raw.get("role") or ""),
        name=str(raw.get("name") or ""),
        label=str(raw.get("label") or ""),
        bbox=_geometry_from_mapping(bbox),
        state=dict(raw.get("state") or {}),
        actions=[str(action) for action in (raw.get("actions") or [])],
        path=str(raw.get("path") or ""),
        confidence=float(raw.get("confidence", 0.0) or 0.0),
    )


def find_semantic_element(envelope: Dict[str, Any], element_id: str) -> SemanticElement:
    """Find and rehydrate a semantic element by stable id from an envelope."""
    for raw in envelope.get("snapshot", {}).get("elements", []) or []:
        if raw.get("element_id") == element_id:
            return semantic_element_from_mapping(raw)
    raise ValueError(f"semantic element not found: {element_id}")


def _coerce_semantic_elements(snapshot: Any) -> List[SemanticElement]:
    """Normalize a semantic envelope, raw element mapping list, or element list."""
    if isinstance(snapshot, dict):
        raw_elements = snapshot.get("snapshot", {}).get("elements", []) or []
    else:
        raw_elements = snapshot or []

    elements: List[SemanticElement] = []
    for raw in raw_elements:
        if isinstance(raw, SemanticElement):
            elements.append(raw)
        else:
            elements.append(semantic_element_from_mapping(raw))
    return elements


def snapshot_diff(old: Any, new: Any) -> Dict[str, Any]:
    """Compare two semantic snapshots and report element-level state changes.

    ``old`` and ``new`` may each be a semantic envelope, a list of
    ``SemanticElement`` instances, or a list of serialized element mappings.
    """
    old_by_id = {element.element_id: element for element in _coerce_semantic_elements(old)}
    new_by_id = {element.element_id: element for element in _coerce_semantic_elements(new)}

    changed: Dict[str, Dict[str, Any]] = {}
    unchanged: List[str] = []
    for element_id in sorted(old_by_id.keys() & new_by_id.keys()):
        state_change = old_by_id[element_id].state_diff(new_by_id[element_id])
        if any(state_change[section] for section in ("changed", "added", "removed")):
            changed[element_id] = state_change
        else:
            unchanged.append(element_id)

    return {
        "changed": changed,
        "added": sorted(new_by_id.keys() - old_by_id.keys()),
        "removed": sorted(old_by_id.keys() - new_by_id.keys()),
        "unchanged": unchanged,
    }


def wait_for_state_change(
    element_id: str,
    expected_state: Dict[str, Any],
    timeout: float,
    poll_interval: float = 0.5,
    *,
    snapshot_builder: Any = None,
    sleeper: Any = time.sleep,
    monotonic: Any = time.monotonic,
    **snapshot_kwargs: Any,
) -> SemanticElement:
    """Poll semantic snapshots until an element reaches the expected state.

    Returns the matching element. Raises ``TimeoutError`` when the expected
    state does not appear before ``timeout`` seconds elapse.
    """
    if snapshot_builder is None:
        snapshot_builder = build_semantic_snapshot
    if timeout < 0:
        raise ValueError("timeout must be greater than or equal to zero")
    if poll_interval < 0:
        raise ValueError("poll_interval must be greater than or equal to zero")

    expected = dict(expected_state or {})
    deadline = monotonic() + float(timeout)
    last_state: Optional[Dict[str, Any]] = None
    while True:
        snapshot = snapshot_builder(**snapshot_kwargs)
        try:
            element = find_semantic_element(snapshot, element_id)
            last_state = dict(element.state or {})
            if all(element.state.get(key) == value for key, value in expected.items()):
                return element
        except ValueError:
            last_state = None

        if monotonic() >= deadline:
            expected_text = ", ".join(f"{key}={value!r}" for key, value in sorted(expected.items()))
            raise TimeoutError(
                f"timed out waiting for {element_id} to reach {expected_text}; last_state={last_state}"
            )
        if poll_interval:
            sleeper(poll_interval)


def _snapshot_id(now: Optional[datetime] = None) -> str:
    now = now or datetime.now(timezone.utc)
    return f"snap_{now.strftime('%Y%m%d')}_{secrets.token_urlsafe(8)[:10].lower()}"


def _role_prefix(role: str) -> str:
    role_l = (role or "element").lower()
    if "button" in role_l:
        return "B"
    if role_l in {"text", "entry", "textbox", "input", "editable text"} or "text" in role_l:
        return "T"
    if "link" in role_l:
        return "L"
    if "menu" in role_l:
        return "M"
    if "checkbox" in role_l or "check" in role_l:
        return "C"
    return "E"


def _geometry_from_window(raw: Dict[str, Any]) -> Geometry:
    return Geometry(
        x=int(raw.get("x", 0) or 0),
        y=int(raw.get("y", 0) or 0),
        width=int(raw.get("width", 0) or 0),
        height=int(raw.get("height", 0) or 0),
    )


def _window_title(raw: Dict[str, Any]) -> str:
    return str(raw.get("title") or raw.get("name") or raw.get("class") or "")


def _window_app(raw: Dict[str, Any]) -> Optional[str]:
    app = raw.get("app_id") or raw.get("class") or raw.get("name")
    return str(app) if app is not None else None


def _build_windows(window_provider: Any, app: Optional[str], window_id: Optional[str]) -> List[SemanticWindow]:
    raw_windows: Iterable[Dict[str, Any]] = []
    if window_provider is not None:
        try:
            raw_windows = window_provider.list_windows() or []
        except Exception:
            raw_windows = []

    windows: List[SemanticWindow] = []
    app_l = app.lower() if app else None
    for index, raw in enumerate(raw_windows, start=1):
        raw_id = str(raw.get("id") or raw.get("window_id") or index)
        title = _window_title(raw)
        app_id = _window_app(raw)
        if window_id and raw_id != str(window_id):
            continue
        if app_l and app_l not in f"{title} {app_id or ''}".lower():
            continue
        windows.append(
            SemanticWindow(
                window_id=f"W{len(windows) + 1}",
                app_id=app_id,
                title=title,
                is_focused=bool(raw.get("is_focused") or raw.get("focused") or len(windows) == 0),
                geometry=_geometry_from_window(raw),
                raw_window_id=raw_id,
            )
        )

    if not windows:
        windows.append(
            SemanticWindow(
                window_id="W1",
                app_id=app,
                title=app or "semantic-source",
                is_focused=True,
                geometry=Geometry(0, 0, 0, 0),
                raw_window_id=window_id,
            )
        )
    return windows


def _element_actions(role: str, attributes: Dict[str, Any]) -> List[str]:
    raw_actions = attributes.get("actions")
    if isinstance(raw_actions, list):
        return [str(action) for action in raw_actions]
    role_l = (role or "").lower()
    actions: List[str] = []
    if "button" in role_l or "link" in role_l or "menu" in role_l or "check" in role_l:
        actions.append("click")
    if "text" in role_l or "entry" in role_l or "input" in role_l:
        actions.extend(["focus", "type"])
    if not actions:
        actions.append("focus")
    return actions


def _element_path(window_id: str, element: Any, element_id: str) -> str:
    parent = getattr(element, "parent", None)
    role = getattr(element, "role", "element") or "element"
    if parent:
        return f"{window_id} > {parent} > {role}[{element_id}]"
    return f"{window_id} > {role}[{element_id}]"


def build_semantic_snapshot(
    *,
    app: Optional[str] = None,
    window_id: Optional[str] = None,
    cache_policy: str = "prefer_live",
    ttl_seconds: int = 30,
    max_elements: int = 60,
    visual: bool = False,
    visual_once: bool = False,
    inspection_provider: Any = None,
    window_provider: Any = None,
) -> Dict[str, Any]:
    """Build the ``peekxd.see.v1`` semantic envelope from provider data."""
    started = time.monotonic()
    created_at = datetime.now(timezone.utc)

    if inspection_provider is None:
        from .inspection import get_inspection_provider

        inspection_provider = get_inspection_provider()
    if window_provider is None:
        from .window import get_window_provider

        window_provider = get_window_provider()

    elements_raw = inspection_provider.get_ui_tree(app) or []
    windows = _build_windows(window_provider, app, window_id)
    primary_window_id = windows[0].window_id
    fallback_used = (
        len(windows) == 1
        and windows[0].geometry == Geometry(0, 0, 0, 0)
        and windows[0].title == (app or "semantic-source")
        and windows[0].app_id == app
    )

    elements: List[SemanticElement] = []
    for index, element in enumerate(elements_raw[: max(0, int(max_elements))], start=1):
        role = str(getattr(element, "role", "element") or "element")
        attrs = dict(getattr(element, "attributes", {}) or {})
        position: Tuple[int, int] = getattr(element, "position", (0, 0)) or (0, 0)
        size: Tuple[int, int] = getattr(element, "size", (0, 0)) or (0, 0)
        element_id = f"{primary_window_id}-{_role_prefix(role)}{index}"
        name = str(getattr(element, "name", "") or "")
        label = str(attrs.get("label") or attrs.get("description") or name)
        state = {
            "enabled": bool(attrs.get("enabled", True)),
            "focused": bool(attrs.get("focused", False)),
        }
        elements.append(
            SemanticElement(
                element_id=element_id,
                raw_element_id=str(getattr(element, "id", index)),
                window_id=primary_window_id,
                role=role,
                name=name,
                label=label,
                bbox=Geometry(int(position[0]), int(position[1]), int(size[0]), int(size[1])),
                state=state,
                actions=_element_actions(role, attrs),
                path=_element_path(primary_window_id, element, element_id),
                confidence=float(attrs.get("confidence", 0.9)),
            )
        )

    elapsed_ms = int((time.monotonic() - started) * 1000)
    missing_apps = [app] if app and not elements else []
    source_fidelity = "low" if not elements else "medium" if fallback_used else "high"
    completeness_score = 0.0 if not elements else 0.75 if fallback_used else 1.0
    source = {
        "kind": "live_accessibility",
        "provider": inspection_provider.__class__.__name__,
        "source_fidelity": source_fidelity,
        "completeness_score": completeness_score,
        "missing_apps": missing_apps,
        "fallback_used": fallback_used,
    }
    if not elements:
        source["warning"] = "live_accessibility_returned_no_elements"
    return {
        "schema_version": SCHEMA_VERSION,
        "command": "see --semantic",
        "request": {
            "app": app,
            "window_id": window_id,
            "cache_policy": cache_policy,
            "ttl_seconds": int(ttl_seconds),
            "max_elements": int(max_elements),
            "visual": bool(visual),
            "visual_once": bool(visual_once),
        },
        "snapshot": {
            "snapshot_id": _snapshot_id(created_at),
            "created_at": created_at.isoformat().replace("+00:00", "Z"),
            "ttl_seconds": int(ttl_seconds),
            "cache_ttl_remaining_seconds": float(ttl_seconds),
            "cached": False,
            "source": source,
            "windows": [asdict(window) for window in windows],
            "elements": [asdict(element) for element in elements],
        },
        "safety_state": {
            "state": "OK",
            "code": "SEMANTIC_OK",
            "reason": "live_accessibility_success",
        },
        "meta": {
            "cache_id": None,
            "cache_hit": False,
            "request_id": f"req_{secrets.token_hex(2)}",
            "elapsed_ms": elapsed_ms,
        },
        "result": {"ok": True, "error": None},
    }


def render_semantic_hud(envelope: Dict[str, Any], *, max_elements: Optional[int] = None) -> str:
    """Render a compact human-readable HUD for semantic snapshots."""
    snapshot = envelope["snapshot"]
    elements = snapshot.get("elements", [])
    shown = elements[:max_elements] if max_elements is not None else elements
    source = snapshot.get("source", {})
    lines = [
        f"snapshot={snapshot['snapshot_id']} schema={SCHEMA_VERSION} source={source.get('kind', 'unknown')} ttl={snapshot.get('ttl_seconds', 0)}s cache=fresh",
    ]
    for window in snapshot.get("windows", []):
        focused = "focused" if window.get("is_focused") else "unfocused"
        lines.append(
            f"window={window.get('window_id')} {focused} app={window.get('app_id') or '-'} title=\"{window.get('title') or ''}\""
        )
    actionable = sum(1 for element in elements if element.get("actions"))
    lines.append(f"elements={len(elements)} shown={len(shown)} actionable={actionable}")
    for element in shown:
        bbox = element.get("bbox", {})
        enabled = "enabled" if element.get("state", {}).get("enabled", True) else "disabled"
        label = element.get("label") or element.get("name") or ""
        lines.append(
            f"{element.get('element_id')} {element.get('role')} {enabled}  \"{label}\" @ ({bbox.get('x', 0)},{bbox.get('y', 0)}) {bbox.get('width', 0)}x{bbox.get('height', 0)}"
        )
    return "\n".join(lines)
