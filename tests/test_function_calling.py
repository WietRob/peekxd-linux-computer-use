"""Tests for function-calling schema parsing and fallback behavior."""

from unittest.mock import patch

from peekxd.agent import function_calling


def test_parse_tool_call_uses_fallback_when_pydantic_is_unavailable():
    """Known tools should still parse and validate in no-pydantic mode."""
    with patch.object(function_calling, "_HAS_PYDANTIC", False):
        assert function_calling.parse_tool_call("click", '{"x": 10, "y": 20}') == {
            "x": 10,
            "y": 20,
        }
        assert function_calling.parse_tool_call("unknown", "{bad json") == {}
        assert function_calling.parse_tool_call("unknown", None) == {}


def test_parse_tool_call_fallback_rejects_missing_or_wrong_typed_known_fields():
    """Fallback mode must not silently accept malformed known tool params."""
    with patch.object(function_calling, "_HAS_PYDANTIC", False):
        for payload in ('{"x": 10}', '{"x": "10", "y": 20}', None, "{bad json"):
            try:
                function_calling.parse_tool_call("click", payload)
            except ValueError as exc:
                assert "Validation failed for click" in str(exc)
            else:
                raise AssertionError(f"expected validation failure for {payload!r}")


def test_get_tool_schemas_json_returns_fallback_schema_without_pydantic():
    """Fallback schema builder should preserve tool fields and required flags."""
    with patch.object(function_calling, "_HAS_PYDANTIC", False):
        schema_list = function_calling.get_tool_schemas_json()

    click_schema = next(
        item["function"]
        for item in schema_list
        if item["function"]["name"] == "peekxd_click"
    )
    properties = click_schema["parameters"]["properties"]

    assert properties["x"]["type"] == "integer"
    assert properties["y"]["type"] == "integer"
    assert properties["button"]["type"] == "string"
    assert properties["button"]["default"] == "left"
    assert set(click_schema["parameters"]["required"]) == {"x", "y"}
