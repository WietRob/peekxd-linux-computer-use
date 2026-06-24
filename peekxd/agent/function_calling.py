"""Structured function calling for peekxd Linux.

Replaces prompt-based JSON extraction with proper Pydantic models
for robust tool calling with validation and retries.
"""

import inspect
import json
from typing import Any, Dict, List, Optional, Type, get_args, get_origin


class _FallbackField:
    """Container for fallback ``Field(...)`` metadata when pydantic is absent."""

    __slots__ = ("default", "description")

    def __init__(self, default: Any = object(), description: Optional[str] = None):
        self.default = default
        self.description = description


_UNSET = object()

try:
    from pydantic import BaseModel, Field, ValidationError
    _HAS_PYDANTIC = True
except ImportError:
    _HAS_PYDANTIC = False

    class BaseModel:
        """Minimal fallback base when pydantic is unavailable."""

        def __init__(self, **kwargs: Any):
            self.__dict__.update(kwargs)

        @classmethod
        def model_json_schema(cls) -> Dict[str, Any]:
            return {}

        def model_dump(self, exclude_none: bool = False) -> Dict[str, Any]:
            if not exclude_none:
                return dict(self.__dict__)
            return {key: value for key, value in self.__dict__.items() if value is not None}

    class ValidationError(Exception):
        pass

    def Field(default: Any = _UNSET, **kwargs: Any) -> Any:
        """Fallback Field stub when pydantic is not installed."""
        return _FallbackField(default=default, description=kwargs.get("description"))


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
    schema = TOOL_SCHEMAS.get(tool_name)

    if not _HAS_PYDANTIC:
        # Fallback: no Pydantic, keep legacy JSON parsing but still validate
        # known tools against their lightweight annotation-derived schema.
        parsed = _parse_fallback(params_raw)
        if schema is None:
            return parsed
        try:
            return _validate_fallback_params(schema, parsed)
        except ValueError as exc:
            raise ValueError(f"Validation failed for {tool_name}: {exc}") from exc

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
    if not _HAS_PYDANTIC:
        schemas = []
        for name, model_class in TOOL_SCHEMAS.items():
            schema = _infer_fallback_schema(model_class)
            schemas.append(
                {
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
                },
            )
        return schemas

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


def _infer_fallback_schema(model_class: Type[Any]) -> Dict[str, Any]:
    """Build lightweight JSON schema metadata from type annotations."""
    annotations = dict(getattr(model_class, "__annotations__", {}))
    properties: Dict[str, Any] = {}
    required: List[str] = []

    for field_name, annotation in annotations.items():
        default = _infer_fallback_default(model_class, field_name)
        description = _infer_fallback_description(model_class, field_name)
        field_type = _annotation_type_name(annotation)
        is_optional = _is_optional_annotation(annotation)
        if default in (None, inspect._empty) and not is_optional:
            required.append(field_name)

        field_spec: Dict[str, Any] = {"type": field_type}
        if default is not inspect._empty:
            field_spec["default"] = default
        if description is not None:
            field_spec["description"] = description
        properties[field_name] = field_spec

    return {
        "description": f"Execute {model_class.__name__.replace('Params', '').lower()}",
        "properties": properties,
        "required": required,
    }


def _infer_fallback_default(model_class: Type[Any], field_name: str) -> Any:
    """Infer fallback default while handling pydantic-v2, pydantic-v1, and shim classes."""
    value = getattr(model_class, field_name, inspect._empty)
    if isinstance(value, _FallbackField):
        if value.default is _UNSET:
            return inspect._empty
        return value.default

    if hasattr(model_class, "model_fields"):
        field = model_class.model_fields.get(field_name)
        if field is not None:
            if hasattr(field, "is_required") and field.is_required():
                return inspect._empty
            default = getattr(field, "default", inspect._empty)
            default_cls = getattr(default, "__class__", None)
            if default_cls is not None and default_cls.__name__ == "PydanticUndefined":
                return inspect._empty
            return default

    if hasattr(model_class, "__fields__"):
        field = model_class.__fields__.get(field_name)
        if field is not None:
            if getattr(field, "required", False):
                return inspect._empty
            return getattr(field, "default", inspect._empty)

    return getattr(model_class, field_name, inspect._empty)


def _infer_fallback_description(model_class: Type[Any], field_name: str) -> Optional[str]:
    """Read fallback field descriptions from shim metadata."""
    value = getattr(model_class, field_name, inspect._empty)
    if isinstance(value, _FallbackField):
        return value.description

    if hasattr(model_class, "model_fields"):
        field = model_class.model_fields.get(field_name)
        if field is not None:
            return getattr(field, "description", None)

    if hasattr(model_class, "__fields__"):
        field = model_class.__fields__.get(field_name)
        if field is not None:
            return field.field_info.description

    return None


def _validate_fallback_params(model_class: Type[Any], params_raw: Dict[str, Any]) -> Dict[str, Any]:
    """Validate parsed params against lightweight fallback schema metadata."""
    if not isinstance(params_raw, dict):
        raise ValueError("Expected dict parameters")

    annotations = dict(getattr(model_class, "__annotations__", {}))
    schema = _infer_fallback_schema(model_class)
    required = set(schema.get("required", []))
    missing = required - set(params_raw.keys())
    if missing:
        raise ValueError(f"Missing required fields for {model_class.__name__}: {sorted(missing)}")

    for field_name, annotation in annotations.items():
        if field_name not in params_raw:
            continue
        if not _value_matches_annotation(params_raw[field_name], annotation):
            raise ValueError(f"Invalid value for {field_name} in {model_class.__name__}")

    return params_raw


def _annotation_type_name(annotation: Any) -> str:
    """Map common Python type hints to JSON schema primitive names."""
    if annotation is int:
        return "integer"
    if annotation is float:
        return "number"
    if annotation is bool:
        return "boolean"
    if annotation is str:
        return "string"
    if annotation is Any:
        return "object"

    origin = get_origin(annotation)
    args = get_args(annotation)
    if origin is None:
        return "string"

    if args and type(None) in args:
        non_null = [arg for arg in args if arg is not type(None)]
        if len(non_null) == 1:
            return _annotation_type_name(non_null[0])

    if origin is list or origin is List:
        return "array"
    if origin is dict:
        return "object"
    if origin is tuple:
        return "array"

    return "string"


def _is_optional_annotation(annotation: Any) -> bool:
    """Detect Optional[...] and Union[..., None] annotations."""
    args = get_args(annotation)
    return bool(args and type(None) in args)


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


def _value_matches_annotation(value: Any, annotation: Any) -> bool:
    """Best-effort runtime type check for the no-pydantic fallback path."""
    if value is None:
        return _is_optional_annotation(annotation)

    if annotation is Any:
        return True
    if annotation is int:
        return isinstance(value, int) and not isinstance(value, bool)
    if annotation is float:
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if annotation is bool:
        return isinstance(value, bool)
    if annotation is str:
        return isinstance(value, str)

    origin = get_origin(annotation)
    args = get_args(annotation)
    if args and type(None) in args:
        return any(
            _value_matches_annotation(value, arg)
            for arg in args
            if arg is not type(None)
        )
    if origin in (list, List):
        if not isinstance(value, list):
            return False
        if not args:
            return True
        return all(_value_matches_annotation(item, args[0]) for item in value)
    if origin is dict:
        return isinstance(value, dict)

    return True


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
