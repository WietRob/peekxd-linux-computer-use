"""Structured function calling for peekxd Linux.

Replaces prompt-based JSON extraction with proper Pydantic models
for robust tool calling with validation and retries.
"""

import json
from typing import Any, Dict, List, Optional, Type

try:
    from pydantic import BaseModel, Field, ValidationError
except ImportError:
    BaseModel = None
    ValidationError = Exception


class ClickParams(BaseModel):
    """Parameters for click action."""
    x: int = Field(description="X coordinate")
    y: int = Field(description="Y coordinate")
    button: str = Field(default="left", description="Mouse button")


class TypeParams(BaseModel):
    """Parameters for type action."""
    text: str = Field(description="Text to type")


class KeyParams(BaseModel):
    """Parameters for key press action."""
    key: Optional[str] = Field(default=None, description="Single key name")
    hotkey: Optional[List[str]] = Field(default=None, description="Hotkey combination")


class MoveParams(BaseModel):
    """Parameters for mouse move."""
    x: int = Field(description="X coordinate")
    y: int = Field(description="Y coordinate")


class ScrollParams(BaseModel):
    """Parameters for scroll."""
    direction: str = Field(default="down", description="Scroll direction")
    amount: int = Field(default=3, description="Scroll amount")


class CaptureParams(BaseModel):
    """Parameters for screenshot capture."""
    mode: str = Field(default="screen", description="Capture mode")
    output_path: Optional[str] = Field(default=None, description="Output file path")


class FindElementParams(BaseModel):
    """Parameters for element finding."""
    description: str = Field(description="Element description")


class WaitParams(BaseModel):
    """Parameters for wait."""
    condition: str = Field(description="Wait condition type")
    description: Optional[str] = Field(default=None, description="What to wait for")
    timeout: float = Field(default=10.0, description="Timeout in seconds")


# Tool registry mapping tool names to Pydantic models
TOOL_SCHEMAS = {
    "click": ClickParams,
    "type": TypeParams,
    "key": KeyParams,
    "move": MoveParams,
    "scroll": ScrollParams,
    "capture": CaptureParams,
    "find_element": FindElementParams,
    "wait": WaitParams,
}


def parse_tool_call(tool_name: str, params_raw: Any) -> Dict[str, Any]:
    """Parse and validate tool parameters using Pydantic models.

    This replaces fragile prompt-based JSON extraction with
    structured validation.

    Args:
        tool_name: Name of the tool.
        params_raw: Raw parameters (dict, JSON string, or None).

    Returns:
        Validated dict of parameters.

    Raises:
        ValueError: If validation fails.
    """
    if BaseModel is None:
        # Fallback: no Pydantic, just basic parsing
        return _parse_fallback(params_raw)

    schema = TOOL_SCHEMAS.get(tool_name)
    if schema is None:
        # Unknown tool — return raw params as-is
        return _parse_fallback(params_raw)

    # Normalize input to dict
    if isinstance(params_raw, str):
        try:
            params_raw = json.loads(params_raw)
        except json.JSONDecodeError:
            raise ValueError(f"Invalid JSON for {tool_name}: {params_raw[:100]}")
    if params_raw is None:
        params_raw = {}
    if not isinstance(params_raw, dict):
        raise ValueError(f"Expected dict for {tool_name}, got {type(params_raw).__name__}")

    try:
        validated = schema(**params_raw)
        return validated.model_dump(exclude_none=True)
    except ValidationError as e:
        errors = [f"{err['loc']}: {err['msg']}" for err in e.errors()]
        raise ValueError(f"Validation failed for {tool_name}: {'; '.join(errors)}")


def get_tool_schemas_json() -> List[Dict[str, Any]]:
    """Get all tool schemas as JSON-compatible dicts.

    Returns tool definitions suitable for OpenAI/Anthropic
    function calling APIs.
    """
    if BaseModel is None:
        return []

    schemas = []
    for name, model_class in TOOL_SCHEMAS.items():
        schema = model_class.model_json_schema()
        schemas.append({
            "type": "function",
            "function": {
                "name": f"peekxd_{name}",
                "description": schema.get("description", f"Execute {name}"),
                "parameters": {
                    "type": "object",
                    "properties": schema.get("properties", {}),
                    "required": schema.get("required", []),
                },
            },
        })
    return schemas


def _parse_fallback(params_raw: Any) -> Dict[str, Any]:
    """Fallback parser when Pydantic is not available."""
    if params_raw is None:
        return {}
    if isinstance(params_raw, dict):
        return params_raw
    if isinstance(params_raw, str):
        try:
            return json.loads(params_raw)
        except json.JSONDecodeError:
            return {}
    return {}


class RobustJSONParser:
    """Robust JSON extraction from LLM responses.

    Handles common failure modes:
    - Markdown code blocks
    - Trailing text after JSON
    - Missing quotes
    - Comments
    """

    @staticmethod
    def extract(response: str) -> Dict[str, Any]:
        """Extract JSON object from potentially messy LLM response.

        Tries multiple strategies in order of reliability.
        """
        if not response or not response.strip():
            return {}

        text = response.strip()

        # Strategy 1: Direct JSON parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Strategy 2: Extract from markdown code block
        if "```" in text:
            try:
                # Find content between ```json ... ```
                parts = text.split("```")
                for i, part in enumerate(parts):
                    clean = part.strip()
                    if clean.lower().startswith("json"):
                        clean = clean[4:].strip()
                    if clean.startswith("{") and clean.endswith("}"):
                        return json.loads(clean)
            except (json.JSONDecodeError, IndexError):
                pass

        # Strategy 3: Find first { ... } pair
        try:
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(text[start:end])
        except json.JSONDecodeError:
            pass

        # Strategy 4: Line-by-line JSON object extraction
        for line in text.split("\n"):
            line = line.strip()
            if line.startswith("{") and line.endswith("}"):
                try:
                    return json.loads(line)
                except json.JSONDecodeError:
                    continue

        # All strategies failed
        raise ValueError(f"Could not extract JSON from response: {text[:200]}...")

    @staticmethod
    def extract_with_retry(response: str, max_retries: int = 0) -> Dict[str, Any]:
        """Extract JSON with optional retry logic.

        If initial extraction fails, tries common fix patterns.
        """
        try:
            return RobustJSONParser.extract(response)
        except ValueError:
            if max_retries <= 0:
                raise

        # Fix attempt 1: Replace single quotes with double quotes
        try:
            fixed = response.replace("'", '"')
            return RobustJSONParser.extract(fixed)
        except ValueError:
            pass

        # Fix attempt 2: Remove trailing commas
        try:
            import re
            fixed = re.sub(r',(\s*[}\]])', r'\1', response)
            return RobustJSONParser.extract(fixed)
        except ValueError:
            pass

        raise ValueError(f"JSON extraction failed after {max_retries} retries")
