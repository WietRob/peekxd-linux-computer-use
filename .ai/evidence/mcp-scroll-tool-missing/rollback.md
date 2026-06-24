# Rollback Plan

Candidate: mcp-scroll-tool-missing
Branch: autonomy/peekxd/mcp-scroll-tool-missing-20260621

## Preferred rollback after merge

Revert the candidate commit with human approval, per the No-Revert policy:

```bash
git revert <commit-sha>
python -m pytest tests/test_mcp.py::TestMCPServer::test_scroll tests/test_mcp.py::TestMCPServer::test_tools_registered -q
python -m pytest tests/ -q
```

## Manual rollback before merge

Remove the additive MCP `scroll` tool from `peekxd/mcp_server/server.py`, then remove the `scroll` expected-tool entry and `test_scroll` from `tests/test_mcp.py`.

## Backup patch

The implementation diff is saved at:

```text
.ai/evidence/mcp-scroll-tool-missing/changes.patch
```
