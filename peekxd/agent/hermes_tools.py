"""Hermes tool definitions for peekxd Linux.

Semantic-first tool surface only. Screenshot/vision capture tools were removed
because visible capture can disturb the user's live desktop.
"""

import json
from typing import Any, Dict, List


def _get_input():
    from ..input import get_input_provider
    return get_input_provider()


def _get_window():
    from ..window import get_window_provider
    return get_window_provider()


def _get_inspection():
    from ..inspection import get_inspection_provider
    return get_inspection_provider()


HERMES_TOOLS = [
    {
        "name": "peekxd_see_semantic",
        "description": "Return semantic UI/window state without screenshots or portal prompts.",
        "parameters": {
            "type": "object",
            "properties": {
                "app_name": {"type": "string"},
                "window_id": {"type": "string"},
                "max_elements": {"type": "integer", "default": 60},
            },
            "required": [],
        },
    },
    {
        "name": "peekxd_click",
        "description": "Click the mouse at explicit coordinates.",
        "parameters": {
            "type": "object",
            "properties": {
                "x": {"type": "integer"},
                "y": {"type": "integer"},
                "button": {"type": "string", "enum": ["left", "right", "middle"], "default": "left"},
            },
            "required": ["x", "y"],
        },
    },
    {
        "name": "peekxd_type",
        "description": "Type text at the current cursor position.",
        "parameters": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
    },
    {
        "name": "peekxd_key",
        "description": "Press a single key or hotkey combination.",
        "parameters": {
            "type": "object",
            "properties": {"key": {"type": "string"}, "hotkey": {"type": "array", "items": {"type": "string"}}},
            "required": [],
        },
    },
    {
        "name": "peekxd_move_mouse",
        "description": "Move the mouse cursor to explicit coordinates.",
        "parameters": {"type": "object", "properties": {"x": {"type": "integer"}, "y": {"type": "integer"}}, "required": ["x", "y"]},
    },
    {
        "name": "peekxd_scroll",
        "description": "Scroll the mouse wheel in a direction.",
        "parameters": {
            "type": "object",
            "properties": {"direction": {"type": "string", "enum": ["up", "down", "left", "right"], "default": "down"}, "amount": {"type": "integer", "default": 3}},
            "required": [],
        },
    },
    {"name": "peekxd_list_windows", "description": "List visible windows.", "parameters": {"type": "object", "properties": {}, "required": []}},
    {
        "name": "peekxd_focus_window",
        "description": "Bring a specific window to the foreground.",
        "parameters": {"type": "object", "properties": {"window_id": {"type": "string"}, "title_contains": {"type": "string"}}, "required": []},
    },
    {
        "name": "peekxd_inspect_ui",
        "description": "Get AT-SPI UI element tree without screenshots.",
        "parameters": {"type": "object", "properties": {"app_name": {"type": "string"}}, "required": []},
    },
]


def get_hermes_tool_definitions() -> List[Dict[str, Any]]:
    return HERMES_TOOLS


def execute_hermes_action(action_name: str, params: Dict[str, Any]) -> str:
    """Execute a peekxd Hermes tool action and return JSON string."""
    try:
        if action_name == "peekxd_see_semantic":
            from ..semantic import build_semantic_snapshot
            result = build_semantic_snapshot(
                app=params.get("app_name"),
                window_id=params.get("window_id"),
                max_elements=int(params.get("max_elements", 60)),
                inspection_provider=_get_inspection(),
                window_provider=_get_window(),
            )
        elif action_name == "peekxd_click":
            _get_input().click(params["x"], params["y"], params.get("button", "left"))
            result = {"success": True, "action": "click", "x": params["x"], "y": params["y"]}
        elif action_name == "peekxd_type":
            _get_input().type_text(params["text"])
            result = {"success": True, "action": "type", "text_length": len(params["text"])}
        elif action_name == "peekxd_key":
            if "hotkey" in params and params["hotkey"]:
                _get_input().hotkey(*params["hotkey"])
                result = {"success": True, "action": "hotkey", "keys": params["hotkey"]}
            else:
                _get_input().key_press(params["key"])
                result = {"success": True, "action": "key", "key": params["key"]}
        elif action_name == "peekxd_move_mouse":
            _get_input().move_mouse(params["x"], params["y"])
            result = {"success": True, "action": "move", "x": params["x"], "y": params["y"]}
        elif action_name == "peekxd_scroll":
            _get_input().scroll(params.get("direction", "down"), params.get("amount", 3))
            result = {"success": True, "action": "scroll"}
        elif action_name == "peekxd_list_windows":
            result = {"success": True, "windows": _get_window().list_windows()}
        elif action_name == "peekxd_focus_window":
            window_id = params.get("window_id")
            if not window_id and params.get("title_contains"):
                title = params["title_contains"].lower()
                for window in _get_window().list_windows():
                    if title in window.get("title", "").lower():
                        window_id = window["id"]
                        break
            if not window_id:
                raise ValueError("window_id or matching title_contains required")
            _get_window().focus_window(window_id)
            result = {"success": True, "action": "focus_window", "window_id": window_id}
        elif action_name == "peekxd_inspect_ui":
            elements = _get_inspection().get_ui_tree(params.get("app_name"))
            result = {"success": True, "elements": [e._asdict() for e in elements]}
        else:
            result = {"success": False, "error": f"Unknown or removed peekxd action: {action_name}"}
    except Exception as exc:
        result = {"success": False, "error": str(exc), "action": action_name}
    return json.dumps(result)
