"""MCP Server for peekxd Linux."""

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from fastmcp import FastMCP
except ImportError:
    FastMCP = None

from ..core import peekxdError
from ..config import ConfigManager

# Lazy imports -- modules will be loaded on first use
_screenshot = None
_input = None
_inspection = None
_window = None
_vision = None


def _get_screenshot():
    global _screenshot
    if _screenshot is None:
        from ..screenshot import get_screenshot_provider
        _screenshot = get_screenshot_provider()
    return _screenshot


def _get_input():
    global _input
    if _input is None:
        from ..input import get_input_provider
        _input = get_input_provider()
    return _input


def _get_inspection():
    global _inspection
    if _inspection is None:
        from ..inspection import get_inspection_provider
        _inspection = get_inspection_provider()
    return _inspection


def _get_window():
    global _window
    if _window is None:
        from ..window import get_window_provider
        _window = get_window_provider()
    return _window


def _get_vision():
    global _vision
    if _vision is None:
        from ..vision import get_vision_provider
        _vision = get_vision_provider()
    return _vision


def create_mcp_server(config: Optional[ConfigManager] = None):
    """Create and configure the FastMCP server."""
    if FastMCP is None:
        raise ImportError("fastmcp not installed. Run: pip install fastmcp")

    mcp = FastMCP("peekxd-linux")

    @mcp.tool()
    def capture_screen(output_path: Optional[str] = None, mode: str = "screen") -> Dict[str, Any]:
        """Capture a screenshot. Mode: screen, window, or active."""
        provider = _get_screenshot()
        if not output_path:
            output_path = str(Path.home() / "peekxd_capture.png")
        if mode == "screen":
            path = provider.capture_screen(output_path)
        elif mode == "window":
            path = provider.capture_window(output_path)
        elif mode == "active":
            path = provider.capture_window(output_path)  # capture active window
        else:
            return {"error": f"Unknown mode: {mode}"}
        return {"success": True, "path": path, "mode": mode}

    @mcp.tool()
    def move_mouse(x: int, y: int) -> Dict[str, Any]:
        """Move mouse to coordinates."""
        _get_input().move_mouse(x, y)
        return {"success": True, "x": x, "y": y}

    @mcp.tool()
    def click(x: int, y: int, button: str = "left") -> Dict[str, Any]:
        """Click at coordinates."""
        _get_input().click(x, y, button)
        return {"success": True, "x": x, "y": y, "button": button}

    @mcp.tool()
    def drag(x1: int, y1: int, x2: int, y2: int) -> Dict[str, Any]:
        """Perform a drag-and-drop operation from (x1,y1) to (x2,y2)."""
        _get_input().drag(x1, y1, x2, y2)
        return {"success": True, "from": {"x": x1, "y": y1}, "to": {"x": x2, "y": y2}}

    @mcp.tool()
    def type_text(text: str) -> Dict[str, Any]:
        """Type text."""
        _get_input().type_text(text)
        return {"success": True, "text": text}

    @mcp.tool()
    def press_key(key: str) -> Dict[str, Any]:
        """Press a key."""
        _get_input().key_press(key)
        return {"success": True, "key": key}

    @mcp.tool()
    def list_windows() -> List[Dict[str, Any]]:
        """List all windows."""
        return _get_window().list_windows()

    @mcp.tool()
    def focus_window(window_id: str) -> Dict[str, Any]:
        """Focus a window."""
        _get_window().focus_window(window_id)
        return {"success": True, "window_id": window_id}

    @mcp.tool()
    def get_ui_tree(app_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get UI element tree."""
        elements = _get_inspection().get_ui_tree(app_name)
        return [e._asdict() for e in elements]

    @mcp.tool()
    def find_element(name: Optional[str] = None, role: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Find a UI element by name or role."""
        elem = _get_inspection().find_element(name=name, role=role)
        return elem._asdict() if elem else None

    @mcp.tool()
    def analyze_image(image_path: str, question: str) -> str:
        """Analyze an image with AI vision."""
        return _get_vision().analyze(image_path, question)

    @mcp.tool()
    def get_active_window() -> Optional[Dict[str, Any]]:
        """Get the currently focused window."""
        return _get_window().get_active_window()

    @mcp.tool()
    def mark_elements(prompt: Optional[str] = None) -> Dict[str, Any]:
        """Capture screen, detect ALL UI elements with AI, draw numbered bounding boxes.
        Returns element list with coordinates and path to marked image.
        USE THIS FIRST when you need to interact with unknown UI."""
        from ..agent.screen_markup import analyze_screen_with_markup
        cap_path = str(Path.home() / f"peekxd_mark_{int(time.time())}.png")
        _get_screenshot().capture_screen(cap_path)
        return analyze_screen_with_markup(cap_path, prompt=prompt)

    @mcp.tool()
    def find_and_click(description: str, button: str = "left") -> Dict[str, Any]:
        """Find an element by description and click it. Combines vision + input."""
        cap_path = str(Path.home() / f"findclick_{int(time.time())}.png")
        _get_screenshot().capture_screen(cap_path)
        coords = _get_vision().find_element(cap_path, description)
        if coords is None:
            return {"success": False, "error": f"Element not found: {description}"}
        _get_input().click(coords[0], coords[1], button)
        return {"success": True, "clicked_at": {"x": coords[0], "y": coords[1]}, "description": description}

    @mcp.tool()
    def type_into_field(field_description: str, text: str) -> Dict[str, Any]:
        """Find a text field by description, click it, and type text."""
        cap_path = str(Path.home() / f"typefield_{int(time.time())}.png")
        _get_screenshot().capture_screen(cap_path)
        coords = _get_vision().find_element(cap_path, field_description)
        if coords is None:
            return {"success": False, "error": f"Field not found: {field_description}"}
        _get_input().click(coords[0], coords[1])
        time.sleep(0.3)
        _get_input().type_text(text)
        return {"success": True, "field": field_description, "typed": text}

    @mcp.tool()
    def wait_for_element(description: str, timeout: float = 10.0) -> Dict[str, Any]:
        """Wait for an element to appear on screen."""
        from ..agent.actions import WaitCondition
        return WaitCondition.for_element(description, timeout)

    @mcp.tool()
    def wait_for_text(text: str, timeout: float = 10.0) -> Dict[str, Any]:
        """Wait for specific text to appear on screen."""
        from ..agent.actions import WaitCondition
        return WaitCondition.for_text(text, timeout)

    @mcp.tool()
    def run_action_sequence(steps_json: str, stop_on_error: bool = True) -> List[Dict[str, Any]]:
        """Execute a sequence of actions. steps_json is a JSON array of action objects.
        Each step: {\"action\": \"click|type|key|wait|capture\", \"params\": {...}}"""
        import json
        from ..agent.actions import ActionSequence
        steps = json.loads(steps_json)
        seq = ActionSequence.from_dict(steps)
        return seq.execute(stop_on_error=stop_on_error)

    @mcp.tool()
    def screen_has_changed(threshold: float = 0.1) -> Dict[str, Any]:
        """Check if the screen has changed since last check."""
        from ..agent.actions import ScreenDiff
        differ = ScreenDiff()
        changed = differ.has_changed(threshold)
        return {"changed": changed, "screenshot_path": differ.last_screenshot}

    return mcp


def main():
    """Run the MCP server."""
    import asyncio
    config = ConfigManager()
    mcp = create_mcp_server(config)
    transport = config.get("mcp.transport", "stdio")
    if transport == "stdio":
        mcp.run(transport="stdio", show_banner=False)
    else:
        port = config.get("mcp.port", 3000)
        mcp.run(transport="sse", port=port, show_banner=False)


if __name__ == "__main__":
    main()
