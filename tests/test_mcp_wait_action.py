"""Tests for MCP semantic wait actions."""

from unittest.mock import MagicMock, patch

from peekxd.config import ConfigManager
from peekxd.mcp_server import create_mcp_server


def _collect_tools(config):
    registered = []

    def capture_tool(func):
        registered.append(func)
        return func

    mock_mcp = MagicMock()
    mock_mcp.tool = MagicMock(return_value=capture_tool)
    with patch("peekxd.mcp_server.server.FastMCP", return_value=mock_mcp):
        create_mcp_server(config)
    return {func.__name__: func for func in registered}


def _snapshot(snapshot_id, elements):
    return {
        "schema_version": "peekxd.see.v1",
        "snapshot": {
            "snapshot_id": snapshot_id,
            "created_at": "2026-06-30T00:00:00Z",
            "ttl_seconds": 30,
            "cache_ttl_remaining_seconds": 30.0,
            "cached": False,
            "source": {"kind": "live_accessibility", "source_fidelity": "high"},
            "windows": [],
            "elements": elements,
        },
        "meta": {"request_id": f"req-{snapshot_id}", "elapsed_ms": 1},
        "result": {"ok": True, "error": None},
    }


def _element(element_id, *, name="", label="", role="button", state=None):
    return {
        "element_id": element_id,
        "raw_element_id": f"raw-{element_id}",
        "window_id": "W1",
        "role": role,
        "name": name,
        "label": label,
        "bbox": {"x": 0, "y": 0, "width": 10, "height": 10},
        "state": state or {"enabled": True, "focused": False},
        "actions": ["click"],
        "path": f"W1 > {role}[{element_id}]",
        "confidence": 0.9,
    }


def test_wait_for_element_polls_semantic_snapshots_and_returns_last_metadata(tmp_path):
    config = ConfigManager(str(tmp_path / "config.json"))
    tools = _collect_tools(config)
    snapshots = iter(
        [
            _snapshot("snap-empty", []),
            _snapshot("snap-ready", [_element("W1-B1", name="Submit", label="Submit")]),
        ]
    )

    with patch(
        "peekxd.mcp_server.server.build_semantic_snapshot",
        side_effect=lambda **_: next(snapshots),
    ):
        result = tools["wait_for_element"]("Submit", timeout=1.0, poll_interval=0)

    assert result["success"] is True
    assert result["found"] is True
    assert result["query"] == "Submit"
    assert result["matched_element"]["element_id"] == "W1-B1"
    assert result["snapshots_observed"] == 2
    assert result["last_snapshot"]["snapshot_id"] == "snap-ready"
    assert result["last_snapshot"]["source"]["source_fidelity"] == "high"
    assert result["last_snapshot"]["meta"]["request_id"] == "req-snap-ready"


def test_wait_for_text_times_out_with_last_observed_semantic_metadata(tmp_path):
    config = ConfigManager(str(tmp_path / "config.json"))
    tools = _collect_tools(config)
    snapshot = _snapshot("snap-last", [_element("W1-T1", name="Loading", label="Loading")])

    with patch("peekxd.mcp_server.server.build_semantic_snapshot", return_value=snapshot):
        result = tools["wait_for_text"]("Done", timeout=0, poll_interval=0)

    assert result["success"] is False
    assert result["found"] is False
    assert result["query"] == "Done"
    assert result["matched_element"] is None
    assert result["snapshots_observed"] == 1
    assert result["last_snapshot"]["snapshot_id"] == "snap-last"
    assert "timed out" in result["error"]
