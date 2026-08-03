"""Tests for JSON Schema parameter validation."""

import pytest

from src.tools.validation import ValidationError, validate_arguments


class TestValidateArguments:
    def test_valid_arguments_pass(self):
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "count": {"type": "integer"},
            },
            "required": ["name"],
            "additionalProperties": False,
        }
        # Should not raise.
        validate_arguments(schema, {"name": "test", "count": 3})

    def test_missing_required_field(self):
        schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        }
        with pytest.raises(ValidationError, match="缺少必填参数"):
            validate_arguments(schema, {})

    def test_wrong_type_string_expected(self):
        schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}},
        }
        with pytest.raises(ValidationError, match="应为 string"):
            validate_arguments(schema, {"name": 123})

    def test_wrong_type_integer_expected(self):
        schema = {
            "type": "object",
            "properties": {"count": {"type": "integer"}},
        }
        with pytest.raises(ValidationError, match="应为 integer"):
            validate_arguments(schema, {"count": "abc"})

    def test_integer_rejects_bool(self):
        schema = {
            "type": "object",
            "properties": {"count": {"type": "integer"}},
        }
        with pytest.raises(ValidationError, match="实际为 boolean"):
            validate_arguments(schema, {"count": True})

    def test_number_accepts_int_and_float(self):
        schema = {
            "type": "object",
            "properties": {"value": {"type": "number"}},
        }
        validate_arguments(schema, {"value": 42})
        validate_arguments(schema, {"value": 3.14})

    def test_additional_properties_rejected(self):
        schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "additionalProperties": False,
        }
        with pytest.raises(ValidationError, match="未知参数"):
            validate_arguments(schema, {"name": "test", "extra": "bad"})

    def test_additional_properties_allowed_by_default(self):
        schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}},
        }
        # Should not raise -- additionalProperties defaults to True.
        validate_arguments(schema, {"name": "test", "extra": "ok"})

    def test_boolean_type(self):
        schema = {
            "type": "object",
            "properties": {"flag": {"type": "boolean"}},
        }
        validate_arguments(schema, {"flag": True})
        with pytest.raises(ValidationError, match="应为 boolean"):
            validate_arguments(schema, {"flag": "yes"})

    def test_array_type(self):
        schema = {
            "type": "object",
            "properties": {"items": {"type": "array"}},
        }
        validate_arguments(schema, {"items": [1, 2, 3]})
        with pytest.raises(ValidationError, match="应为 array"):
            validate_arguments(schema, {"items": "not a list"})

    def test_non_object_arguments(self):
        schema = {"type": "object", "properties": {}}
        with pytest.raises(ValidationError, match="参数必须为对象"):
            validate_arguments(schema, "not a dict")  # type: ignore[arg-type]
