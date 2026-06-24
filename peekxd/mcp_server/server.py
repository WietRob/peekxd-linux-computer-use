"""MCP Server for peekxd Linux.

The default MCP surface is semantic-first. Pixel/screenshot tools are not
registered because visible capture can disturb the user's live desktop on
GNOME/Wayland portal systems.
"""

from typing import Any, Dict, List, Optional

try:
    from fastmcp import FastMCP
except ImportError:
    FastMCP = None

from ..config import ConfigManager
from ..semantic import build_semantic_snapshot

_input = None
_inspection = None
_window = None


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


def create_mcp_server(config: Optional[ConfigManager] = None):
    """Create and configure the FastMCP server."""
    if FastMCP is None:
        raise ImportError("fastmcp not installed. Run: pip install fastmcp")

    mcp = FastMCP("peekxd-linux")

    @mcp.tool()
    def see_semantic(
        app_name: Optional[str] = None,
        window_id: Optional[str] = None,
        cache_policy: str = "prefer_live",
        ttl_seconds: int = 30,
        max_elements: int = 60,
    ) -> Dict[str, Any]:
        """Return semantic UI/window state without screenshots or portal prompts."""
        return build_semantic_snapshot(
            app=app_name,
            window_id=window_id,
            cache_policy=cache_policy,
            ttl_seconds=ttl_seconds,
            max_elements=max_elements,
            visual=False,
            visual_once=False,
            inspection_provider=_get_inspection(),
            window_provider=_get_window(),
        )

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
    def scroll(direction: str = "down", amount: int = 3) -> Dict[str, Any]:
        """Scroll the mouse wheel."""
        _get_input().scroll(direction, amount)
        return {"success": True, "direction": direction, "amount": amount}

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
    def get_active_window() -> Optional[Dict[str, Any]]:
        """Get the currently focused window."""
        return _get_window().get_active_window()

    @mcp.tool()
    def wait_for_element(description: str, timeout: float = 10.0) -> Dict[str, Any]:
        """Wait for an accessible element to appear without screenshot capture."""
        from ..agent.actions import WaitCondition
        return WaitCondition.for_element(description, timeout)

    @mcp.tool()
    def wait_for_text(text: str, timeout: float = 10.0) -> Dict[str, Any]:
        """Wait for accessible text to appear without screenshot capture."""
        from ..agent.actions import WaitCondition
        return WaitCondition.for_text(text, timeout)

    return mcp


def main():
    """Run the MCP server."""
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
