"""MCP Server for peekxd Linux.

The default MCP surface is semantic-first. Pixel/screenshot tools are not
registered because visible capture can disturb the user's live desktop on
GNOME/Wayland portal systems.
"""

import logging
import os
from typing import Any, Callable, Dict, List, Optional

try:
    from fastmcp import FastMCP
except ImportError:
    FastMCP = None

from ..config import ConfigManager
from ..core.audit import get_logger
from ..core.safety import SafetyGuard, SafetyLevel
from ..core.shadow import ShadowRecorder
from ..core.zones import ZoneDecision
from ..semantic import build_semantic_snapshot
from .middleware import SafetyMiddleware

_input = None
_inspection = None
_window = None
logger = logging.getLogger(__name__)


_TRUSTED_BOOTSTRAP_HOSTS = {"", "localhost", "127.0.0.1", "::1"}


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


def _is_truthy(value: Any) -> bool:
    """Return True for explicit truthy config/env values."""
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _is_trusted_local_bootstrap(config: ConfigManager) -> bool:
    """Return whether config explicitly allows trusted local MCP bootstrap."""
    if not _is_truthy(config.get("mcp.trusted_bootstrap", False)):
        return False

    transport = str(config.get("mcp.transport", "stdio")).strip().lower()
    if transport == "stdio":
        return True

    host = str(config.get("mcp.host", "localhost")).strip().lower()
    return host in _TRUSTED_BOOTSTRAP_HOSTS


def _mcp_safety_bypass_enabled(config: ConfigManager) -> bool:
    """Gate legacy MCP safety bypass to explicit trusted local bootstrap."""
    if os.environ.get("PEEKXD_SAFETY_MCP") != "0":
        return False
    if not _is_trusted_local_bootstrap(config):
        return False

    logger.warning(
        "Trusted local MCP bootstrap safety bypass is active; "
        "only use this for local operator-controlled startup."
    )
    return True


def create_mcp_server(config: Optional[ConfigManager] = None):
    """Create and configure the FastMCP server."""
    if FastMCP is None:
        raise ImportError("fastmcp not installed. Run: pip install fastmcp")

    config = config or ConfigManager()
    mcp = FastMCP("peekxd-linux")
    safety_level = config.get("mcp.safety_level", "normal")
    try:
        guard = SafetyGuard(SafetyLevel(str(safety_level).lower()))
    except ValueError:
        guard = SafetyGuard(SafetyLevel.NORMAL)
    audit_logger = get_logger()
    middleware = SafetyMiddleware(
        safety_guard=guard,
        audit_logger=audit_logger,
        shadow_recorder=ShadowRecorder(),
    )
    bypass_safety = _mcp_safety_bypass_enabled(config)

    def safety_tool(func: Callable[..., Any]) -> Callable[..., Any]:
        if bypass_safety:
            return mcp.tool()(func)
        return mcp.tool()(middleware.wrap_tool(func.__name__, func))

    @safety_tool
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

    @safety_tool
    def move_mouse(x: int, y: int) -> Dict[str, Any]:
        """Move mouse to coordinates."""
        _get_input().move_mouse(x, y)
        return {"success": True, "x": x, "y": y}

    @safety_tool
    def click(x: int, y: int, button: str = "left") -> Dict[str, Any]:
        """Click at coordinates."""
        _get_input().click(x, y, button)
        return {"success": True, "x": x, "y": y, "button": button}

    @safety_tool
    def drag(x1: int, y1: int, x2: int, y2: int) -> Dict[str, Any]:
        """Perform a drag-and-drop operation from (x1,y1) to (x2,y2)."""
        _get_input().drag(x1, y1, x2, y2)
        return {"success": True, "from": {"x": x1, "y": y1}, "to": {"x": x2, "y": y2}}

    @safety_tool
    def type_text(text: str) -> Dict[str, Any]:
        """Type text."""
        _get_input().type_text(text)
        return {"success": True, "text": text}

    @safety_tool
    def scroll(direction: str = "down", amount: int = 3) -> Dict[str, Any]:
        """Scroll the mouse wheel."""
        _get_input().scroll(direction, amount)
        return {"success": True, "direction": direction, "amount": amount}

    @safety_tool
    def press_key(key: str) -> Dict[str, Any]:
        """Press a key."""
        _get_input().key_press(key)
        return {"success": True, "key": key}

    @safety_tool
    def list_windows() -> List[Dict[str, Any]]:
        """List all windows."""
        return _get_window().list_windows()

    @safety_tool
    def focus_window(window_id: str) -> Dict[str, Any]:
        """Focus a window."""
        _get_window().focus_window(window_id)
        return {"success": True, "window_id": window_id}

    @safety_tool
    def get_ui_tree(app_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get UI element tree."""
        elements = _get_inspection().get_ui_tree(app_name)
        return [e._asdict() for e in elements]

    @safety_tool
    def find_element(
        name: Optional[str] = None,
        role: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Find a UI element by name or role."""
        elem = _get_inspection().find_element(name=name, role=role)
        return elem._asdict() if elem else None

    @safety_tool
    def get_active_window() -> Optional[Dict[str, Any]]:
        """Get the currently focused window."""
        return _get_window().get_active_window()

    @safety_tool
    def wait_for_element(
        description: str,
        timeout: float = 10.0,
        poll_interval: float = 0.5,
        app_name: Optional[str] = None,
        window_id: Optional[str] = None,
        cache_policy: str = "prefer_live",
        ttl_seconds: int = 30,
        max_elements: int = 60,
    ) -> Dict[str, Any]:
        """Wait for an accessible element to appear without screenshot capture."""
        from ..agent.actions import WaitCondition

        return WaitCondition.for_semantic_element(
            description,
            timeout=timeout,
            poll_interval=poll_interval,
            snapshot_builder=lambda **kwargs: build_semantic_snapshot(
                **kwargs,
                visual=False,
                visual_once=False,
                inspection_provider=_get_inspection(),
                window_provider=_get_window(),
            ),
            app=app_name,
            window_id=window_id,
            cache_policy=cache_policy,
            ttl_seconds=ttl_seconds,
            max_elements=max_elements,
        )

    @safety_tool
    def wait_for_text(
        text: str,
        timeout: float = 10.0,
        poll_interval: float = 0.5,
        app_name: Optional[str] = None,
        window_id: Optional[str] = None,
        cache_policy: str = "prefer_live",
        ttl_seconds: int = 30,
        max_elements: int = 60,
    ) -> Dict[str, Any]:
        """Wait for accessible text to appear without screenshot capture."""
        from ..agent.actions import WaitCondition

        return WaitCondition.for_semantic_text(
            text,
            timeout=timeout,
            poll_interval=poll_interval,
            snapshot_builder=lambda **kwargs: build_semantic_snapshot(
                **kwargs,
                visual=False,
                visual_once=False,
                inspection_provider=_get_inspection(),
                window_provider=_get_window(),
            ),
            app=app_name,
            window_id=window_id,
            cache_policy=cache_policy,
            ttl_seconds=ttl_seconds,
            max_elements=max_elements,
        )

    @safety_tool
    def peekxd_set_safety_level(level: str) -> Dict[str, Any]:
        """Set the MCP SafetyGuard level for subsequent tool calls."""
        normalized = str(level).lower()
        try:
            middleware.safety_guard.level = SafetyLevel(normalized)
        except ValueError:
            return {
                "success": False,
                "error": f"Unknown safety level: {level}",
                "allowed_levels": [item.value for item in SafetyLevel],
            }
        return {"success": True, "safety_level": middleware.safety_guard.level.value}

    @safety_tool
    def peekxd_ghost_preview(action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Return a structured GHOST preview for an action without executing it."""
        decision = middleware.safety_guard.check_zone(action, params)
        preview = ZoneDecision.create_ghost_preview(action, params, decision)
        return {"preview": preview.to_dict(), "decision": decision.to_dict()}

    @safety_tool
    def peekxd_audit_export(path: Optional[str] = None) -> Dict[str, Any]:
        """Export the current MCP audit log to JSON."""
        export_path = middleware.audit_logger.export_json(path)
        return {"success": True, "path": export_path}

    @safety_tool
    def peekxd_zone_check(action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Return the SafetyGuard zone decision for an action without executing it."""
        decision = middleware.safety_guard.check_zone(action, params)
        return {"decision": decision.to_dict()}

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
