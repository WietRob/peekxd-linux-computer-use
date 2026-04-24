"""Example: Connect to the MCP server."""
# Run: peekxd mcp
# Then connect with any MCP client (Claude Desktop, Cursor, etc.)
# Tools available:
#   capture_screen, move_mouse, click, type_text
#   press_key, list_windows, focus_window
#   get_ui_tree, find_element, analyze_image

# Or use programmatically:
from peekxd.mcp_server import create_mcp_server
from peekxd.config import ConfigManager

server = create_mcp_server(ConfigManager())
print("MCP server created with tools:")
print("  - capture_screen")
print("  - move_mouse")
print("  - click")
print("  - type_text")
print("  - press_key")
print("  - list_windows")
print("  - focus_window")
print("  - get_ui_tree")
print("  - find_element")
print("  - analyze_image")
print("  - get_active_window")
