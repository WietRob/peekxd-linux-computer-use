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
            "source": {
                "kind": "live_accessibility",
                "provider": inspection_provider.__class__.__name__,
                "source_fidelity": "medium",
            },
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
