# Evidence

Candidate: mcp-scroll-tool-missing
Branch: autonomy/peekxd/mcp-scroll-tool-missing-20260621

## What changed

- Added an MCP `scroll(direction="down", amount=3)` tool in `peekxd/mcp_server/server.py`.
- The tool delegates directly to the existing input provider `scroll(direction, amount)` capability.
- Added MCP tests in `tests/test_mcp.py` to verify registration and delegation.

## Why

The input provider abstraction already defines `scroll`, but the MCP server did not expose it. Registering the additive tool enables MCP clients to scroll pages, panels, and documents without changing existing tool behavior.

## Files changed

- `peekxd/mcp_server/server.py`
- `tests/test_mcp.py`
- `.ai/evidence/mcp-scroll-tool-missing/changes.patch`
- `.ai/evidence/mcp-scroll-tool-missing/tests.md`
- `.ai/evidence/mcp-scroll-tool-missing/rollback.md`
- `.ai/evidence/mcp-scroll-tool-missing/evidence.md`

## Verification

- RED: `python -m pytest tests/test_mcp.py::TestMCPServer::test_scroll -q` failed before implementation because no `scroll` MCP tool was registered.
- GREEN targeted: `python -m pytest tests/test_mcp.py::TestMCPServer::test_scroll tests/test_mcp.py::TestMCPServer::test_tools_registered -q` passed.
- Full suite: `python -m pytest tests/ -q` passed with 481 tests.
