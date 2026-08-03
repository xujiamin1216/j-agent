"""Lightweight JSON Schema validation for tool parameters.

This module provides a minimal validator that covers the most common
JSON Schema subset used by tool definitions: type checking, required
fields, and additionalProperties. It avoids pulling in the full
``jsonschema`` library dependency.

When validation fails, a ``ValidationError`` is raised. The
``ToolRegistry`` catches this and returns it as an ``is_error=True``
``ToolResult`` with a clear, actionable message.
"""

from __future__ import annotations

from typing import Any


class ValidationError(Exception):
    """Raised when tool arguments do not match the parameter JSON Schema."""


# Mapping from JSON Schema type names to Python types.
# Note: JSON "integer" accepts Python bool=False/True as well since
# bool is a subclass of int, so we check bool separately for integer.
_TYPE_MAP: dict[str, tuple[type, ...]] = {
    "string": (str,),
    "integer": (int,),
    "number": (int, float),
    "boolean": (bool,),
    "array": (list,),
    "object": (dict,),
}


def validate_arguments(parameters: dict[str, Any], arguments: dict[str, Any]) -> None:
    """Validate *arguments* against a tool's JSON Schema *parameters*.

    Raises ``ValidationError`` with a descriptive message if any check
    fails. Returns ``None`` on success.
    """
    schema_type = parameters.get("type", "object")
    if schema_type != "object":
        raise ValidationError(
            f"工具参数 schema 顶层 type 必须为 'object', 实际为 '{schema_type}'"
        )

    if not isinstance(arguments, dict):
        raise ValidationError(
            f"参数必须为对象, 实际类型为 {type(arguments).__name__}"
        )

    properties = parameters.get("properties", {})
    required = parameters.get("required", [])

    # Check required fields.
    for field in required:
        if field not in arguments:
            raise ValidationError(f"缺少必填参数: '{field}'")

    # Check additionalProperties.
    allow_additional = parameters.get("additionalProperties", True)
    if not allow_additional:
        unknown = set(arguments.keys()) - set(properties.keys())
        if unknown:
            raise ValidationError(
                f"存在未知参数: {', '.join(sorted(unknown))}"
            )

    # Check each provided field's type.
    for field, value in arguments.items():
        if field not in properties:
            continue  # already handled by additionalProperties check
        field_schema = properties[field]
        expected_type = field_schema.get("type")
        if expected_type is None:
            continue  # no type constraint
        _check_type(field, value, expected_type)


def _check_type(field: str, value: Any, expected_type: str) -> None:
    """Check that *value* matches *expected_type* (a JSON Schema type name)."""
    if expected_type not in _TYPE_MAP:
        return  # unknown type, skip

    # Special case: bool is a subclass of int in Python, but JSON treats
    # them as distinct types. An "integer" field should not accept bools.
    if expected_type == "integer" and isinstance(value, bool):
        raise ValidationError(
            f"参数 '{field}' 应为 integer, 实际为 boolean"
        )
    if expected_type == "number" and isinstance(value, bool):
        raise ValidationError(
            f"参数 '{field}' 应为 number, 实际为 boolean"
        )

    accepted = _TYPE_MAP[expected_type]
    if not isinstance(value, accepted):
        actual = type(value).__name__
        raise ValidationError(
            f"参数 '{field}' 应为 {expected_type}, 实际为 {actual}"
        )
