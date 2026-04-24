"""Hermes tool definitions for peekxd Linux.

Provides tool schemas and execution functions for direct Hermes agent integration.
Hermes agents can call these tools by name with JSON parameters.
"""

import json
import os
import tempfile
import time
from typing import Any, Dict, List, Optional

from ..core.errors import peekxdError


# =============================================================================
# Lazy provider getters (patchable for testing)
# =============================================================================

def _get_screenshot():
    from ..screenshot import get_screenshot_provider
    return get_screenshot_provider()

def _get_input():
    from ..input import get_input_provider
    return get_input_provider()

def _get_window():
    from ..window import get_window_provider
    return get_window_provider()

def _get_vision():
    from ..vision import get_vision_provider
    return get_vision_provider()

def _get_inspection():
    from ..inspection import get_inspection_provider
    return get_inspection_provider()


# =============================================================================
# Hermes Tool Schema Definitions
# =============================================================================

HERMES_TOOLS = [
    {
        "name": "peekxd_capture_screen",
        "description": "Capture a screenshot of the entire screen, a specific window, or a region. Returns the path to the saved image file.",
        "parameters": {
            "type": "object",
            "properties": {
                "mode": {
                    "type": "string",
                    "enum": ["screen", "window", "region"],
                    "description": "Capture mode: 'screen' for full screen, 'window' for active/specific window, 'region' for a specific area",
                    "default": "screen",
                },
                "output_path": {
                    "type": "string",
                    "description": "Optional path to save the screenshot. If not provided, a temp file is used.",
                },
                "x": {"type": "integer", "description": "X coordinate for region mode"},
                "y": {"type": "integer", "description": "Y coordinate for region mode"},
                "width": {"type": "integer", "description": "Width for region mode"},
                "height": {"type": "integer", "description": "Height for region mode"},
                "window_id": {"type": "string", "description": "Window ID for window mode"},
            },
            "required": [],
        },
    },
    {
        "name": "peekxd_analyze_screen",
        "description": "Capture a screenshot and analyze it with AI vision. Returns a detailed description of what is visible on the screen, including UI elements, text, and layout.",
        "parameters": {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "Specific question or analysis prompt. Default: 'Describe the current screen in detail, including all visible UI elements, text, buttons, and their approximate positions.'",
                },
            },
            "required": [],
        },
    },
    {
        "name": "peekxd_find_element",
        "description": "Find the screen coordinates of a UI element by description. Returns x,y coordinates that can be used with click actions.",
        "parameters": {
            "type": "object",
            "properties": {
                "description": {
                    "type": "string",
                    "description": "Description of the element to find, e.g., 'the red Submit button', 'text field labeled Username', 'close button in top right'",
                },
            },
            "required": ["description"],
        },
    },
    {
        "name": "peekxd_click",
        "description": "Click the mouse at specific coordinates or on a described element.",
        "parameters": {
            "type": "object",
            "properties": {
                "x": {"type": "integer", "description": "X coordinate"},
                "y": {"type": "integer", "description": "Y coordinate"},
                "element_description": {
                    "type": "string",
                    "description": "Alternative to x,y: describe the element to click and coordinates will be found automatically",
                },
                "button": {
                    "type": "string",
                    "enum": ["left", "right", "middle"],
                    "default": "left",
                    "description": "Mouse button to click",
                },
            },
            "required": [],
        },
    },
    {
        "name": "peekxd_type",
        "description": "Type text at the current cursor position.",
        "parameters": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Text to type",
                },
            },
            "required": ["text"],
        },
    },
    {
        "name": "peekxd_key",
        "description": "Press a single key or a hotkey combination.",
        "parameters": {
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "description": "Key name, e.g., 'Return', 'Escape', 'Tab', 'ctrl', 'alt', 'shift'",
                },
                "hotkey": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Hotkey combination as array, e.g., ['ctrl', 'c'], ['alt', 'Tab']",
                },
            },
            "required": [],
        },
    },
    {
        "name": "peekxd_move_mouse",
        "description": "Move the mouse cursor to specific coordinates.",
        "parameters": {
            "type": "object",
            "properties": {
                "x": {"type": "integer", "description": "X coordinate"},
                "y": {"type": "integer", "description": "Y coordinate"},
            },
            "required": ["x", "y"],
        },
    },
    {
        "name": "peekxd_scroll",
        "description": "Scroll the mouse wheel in a direction.",
        "parameters": {
            "type": "object",
            "properties": {
                "direction": {
                    "type": "string",
                    "enum": ["up", "down", "left", "right"],
                    "default": "down",
                },
                "amount": {
                    "type": "integer",
                    "default": 3,
                    "description": "Number of scroll units",
                },
            },
            "required": [],
        },
    },
    {
        "name": "peekxd_list_windows",
        "description": "List all visible windows with their IDs, titles, and positions. Useful for finding window IDs to focus or manipulate.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "peekxd_focus_window",
        "description": "Bring a specific window to the foreground.",
        "parameters": {
            "type": "object",
            "properties": {
                "window_id": {
                    "type": "string",
                    "description": "Window ID from list_windows",
                },
                "title_contains": {
                    "type": "string",
                    "description": "Alternative: focus window whose title contains this text",
                },
            },
            "required": [],
        },
    },
    {
        "name": "peekxd_inspect_ui",
        "description": "Get the UI element tree of the current screen or a specific application. Returns all interactive elements with their names, roles, and positions.",
        "parameters": {
            "type": "object",
            "properties": {
                "app_name": {
                    "type": "string",
                    "description": "Optional: filter to a specific application",
                },
            },
            "required": [],
        },
    },
    {
        "name": "peekxd_wait",
        "description": "Wait for a condition: element appearance, text visibility, or screen stability. Returns whether the condition was met and how long it took.",
        "parameters": {
            "type": "object",
            "properties": {
                "condition": {
                    "type": "string",
                    "enum": ["element", "text", "stable", "change"],
                    "description": "What to wait for: 'element' = element appears, 'text' = text visible, 'stable' = screen stops changing, 'change' = screen changes",
                },
                "description": {
                    "type": "string",
                    "description": "For element/text conditions: what to look for",
                },
                "timeout": {
                    "type": "number",
                    "default": 10.0,
                    "description": "Maximum seconds to wait",
                },
            },
            "required": ["condition"],
        },
    },
    {
        "name": "peekxd_run_sequence",
        "description": "Execute a sequence of actions (click, type, key, wait, capture) atomically. Each step can have retries and delays. Useful for complex multi-step operations.",
        "parameters": {
            "type": "object",
            "properties": {
                "steps": {
                    "type": "array",
                    "description": "Array of action steps",
                    "items": {
                        "type": "object",
                        "properties": {
                            "action": {
                                "type": "string",
                                "enum": ["click", "find_click", "type", "key", "hotkey", "move", "scroll", "wait", "capture"],
                            },
                            "params": {"type": "object"},
                            "description": {"type": "string"},
                            "retry": {"type": "integer", "default": 1},
                            "delay_after": {"type": "number", "default": 0.5},
                        },
                        "required": ["action"],
                    },
                },
                "stop_on_error": {
                    "type": "boolean",
                    "default": True,
                },
            },
            "required": ["steps"],
        },
    },
    {
        "name": "peekxd_mark_elements",
        "description": "Capture the screen, use AI to detect all UI elements, draw numbered bounding boxes around them, and return both the marked image and element list. This is the MOST POWERFUL tool for understanding the screen — use it first when you need to interact with unknown UI.",
        "parameters": {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "Optional custom detection prompt. Default detects all interactive elements.",
                },
            },
            "required": [],
        },
    },
]


def get_hermes_tool_definitions() -> List[Dict[str, Any]]:
    """Return the full list of Hermes tool definitions.

    Hermes agents should pass these definitions to the LLM so it knows
    which tools are available and what parameters they accept.
    """
    return HERMES_TOOLS.copy()


# =============================================================================
# Tool Execution
# =============================================================================

def execute_hermes_action(tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a Hermes tool action by name.

    This is the main entry point for Hermes agents. The agent calls this
    function with the tool name and parameters from the LLM response.

    Args:
        tool_name: The name of the tool to execute (e.g., 'peekxd_click').
        params: The parameters dict for the tool.

    Returns:
        Dict with 'success', 'result', and optionally 'error'.
    """
    try:
        result = _dispatch_action(tool_name, params)
        return {"success": True, "result": result}
    except peekxdError as e:
        return {"success": False, "error": e.message, "details": e.details}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _dispatch_action(name: str, params: Dict[str, Any]) -> Any:
    """Dispatch to the appropriate action handler."""
    dispatchers = {
        "peekxd_capture_screen": _action_capture_screen,
        "peekxd_analyze_screen": _action_analyze_screen,
        "peekxd_find_element": _action_find_element,
        "peekxd_click": _action_click,
        "peekxd_type": _action_type,
        "peekxd_key": _action_key,
        "peekxd_move_mouse": _action_move_mouse,
        "peekxd_scroll": _action_scroll,
        "peekxd_list_windows": _action_list_windows,
        "peekxd_focus_window": _action_focus_window,
        "peekxd_inspect_ui": _action_inspect_ui,
        "peekxd_wait": _action_wait,
        "peekxd_run_sequence": _action_run_sequence,
        "peekxd_mark_elements": _action_mark_elements,
    }

    handler = dispatchers.get(name)
    if handler is None:
        raise peekxdError(f"Unknown tool: {name}. Available: {list(dispatchers.keys())}")

    return handler(params)


# --- Individual Action Handlers ---

def _action_capture_screen(params: Dict[str, Any]) -> Dict[str, Any]:
    provider = _get_screenshot()
    mode = params.get("mode", "screen")
    output_path = params.get("output_path") or os.path.join(
        tempfile.gettempdir(), f"peekxd_cap_{int(time.time())}.png"
    )

    if mode == "screen":
        path = provider.capture_screen(output_path)
    elif mode == "window":
        path = provider.capture_window(output_path, params.get("window_id"))
    elif mode == "region":
        path = provider.capture_region(
            output_path,
            params.get("x", 0),
            params.get("y", 0),
            params.get("width", 100),
            params.get("height", 100),
        )
    else:
        raise peekxdError(f"Unknown capture mode: {mode}")

    return {"path": path, "mode": mode}


def _action_analyze_screen(params: Dict[str, Any]) -> str:
    screenshot = _get_screenshot()
    vision = _get_vision()

    cap_path = os.path.join(tempfile.gettempdir(), f"analyze_{int(time.time())}.png")
    screenshot.capture_screen(cap_path)

    prompt = params.get("prompt") or (
        "Describe the current screen in detail, including all visible UI elements, "
        "text, buttons, input fields, menus, and their approximate positions. "
        "Be specific about what can be clicked or interacted with."
    )
    return vision.analyze(cap_path, prompt)


def _action_find_element(params: Dict[str, Any]) -> Dict[str, Any]:
    screenshot = _get_screenshot()
    vision = _get_vision()

    cap_path = os.path.join(tempfile.gettempdir(), f"find_{int(time.time())}.png")
    screenshot.capture_screen(cap_path)

    coords = vision.find_element(cap_path, params["description"])
    if coords is None:
        return {"found": False, "description": params["description"]}
    return {"found": True, "x": coords[0], "y": coords[1], "description": params["description"]}


def _action_click(params: Dict[str, Any]) -> Dict[str, Any]:
    input_provider = _get_input()

    # If element_description provided, find coordinates first
    if "element_description" in params:
        screenshot = _get_screenshot()
        vision = _get_vision()
        cap_path = os.path.join(tempfile.gettempdir(), f"click_find_{int(time.time())}.png")
        screenshot.capture_screen(cap_path)
        coords = vision.find_element(cap_path, params["element_description"])
        if coords is None:
            raise peekxdError(f"Element not found: {params['element_description']}")
        x, y = coords
    else:
        x = params.get("x", 0)
        y = params.get("y", 0)

    button = params.get("button", "left")
    input_provider.click(x, y, button)
    return {"clicked": True, "x": x, "y": y, "button": button}


def _action_type(params: Dict[str, Any]) -> Dict[str, Any]:
    input_provider = _get_input()
    text = params["text"]
    input_provider.type_text(text)
    return {"typed": True, "text": text[:50], "length": len(text)}


def _action_key(params: Dict[str, Any]) -> Dict[str, Any]:
    input_provider = _get_input()

    if "hotkey" in params:
        keys = params["hotkey"]
        input_provider.hotkey(*keys)
        return {"pressed": True, "hotkey": keys}
    else:
        key = params.get("key", "")
        input_provider.key_press(key)
        return {"pressed": True, "key": key}


def _action_move_mouse(params: Dict[str, Any]) -> Dict[str, Any]:
    input_provider = _get_input()
    x, y = params["x"], params["y"]
    input_provider.move_mouse(x, y)
    return {"moved": True, "x": x, "y": y}


def _action_scroll(params: Dict[str, Any]) -> Dict[str, Any]:
    input_provider = _get_input()
    direction = params.get("direction", "down")
    amount = params.get("amount", 3)
    input_provider.scroll(direction, amount)
    return {"scrolled": True, "direction": direction, "amount": amount}


def _action_list_windows(params: Dict[str, Any]) -> List[Dict[str, Any]]:
    return _get_window().list_windows()


def _action_focus_window(params: Dict[str, Any]) -> Dict[str, Any]:
    provider = _get_window()

    if "title_contains" in params:
        windows = provider.list_windows()
        target = next(
            (w for w in windows if params["title_contains"].lower() in w.get("title", "").lower()),
            None,
        )
        if target is None:
            raise peekxdError(f"No window with title containing: {params['title_contains']}")
        window_id = str(target["id"])
    else:
        window_id = params.get("window_id", "")

    provider.focus_window(window_id)
    return {"focused": True, "window_id": window_id}


def _action_inspect_ui(params: Dict[str, Any]) -> List[Dict[str, Any]]:
    elements = _get_inspection().get_ui_tree(params.get("app_name"))
    return [e._asdict() for e in elements[:100]]


def _action_wait(params: Dict[str, Any]) -> Dict[str, Any]:
    from .actions import WaitCondition

    condition = params.get("condition", "stable")
    timeout = params.get("timeout", 10.0)
    description = params.get("description", "")

    if condition == "element":
        return WaitCondition.for_element(description, timeout)
    elif condition == "text":
        return WaitCondition.for_text(description, timeout)
    elif condition == "stable":
        return WaitCondition.for_no_change(timeout)
    elif condition == "change":
        from .actions import ScreenDiff
        differ = ScreenDiff()
        return differ.wait_for_change(timeout)
    else:
        raise peekxdError(f"Unknown wait condition: {condition}")


def _action_run_sequence(params: Dict[str, Any]) -> List[Dict[str, Any]]:
    from .actions import ActionSequence

    seq = ActionSequence.from_dict(params["steps"])
    stop_on_error = params.get("stop_on_error", True)
    return seq.execute(stop_on_error=stop_on_error)


def _action_mark_elements(params: Dict[str, Any]) -> Dict[str, Any]:
    from .screen_markup import analyze_screen_with_markup

    screenshot = _get_screenshot()
    cap_path = os.path.join(tempfile.gettempdir(), f"mark_{int(time.time())}.png")
    screenshot.capture_screen(cap_path)

    return analyze_screen_with_markup(cap_path, prompt=params.get("prompt"))
