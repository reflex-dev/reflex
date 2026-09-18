"""Check the SDK's hand-written models against the OpenAPI schema snapshot."""

from __future__ import annotations

import dataclasses
import datetime
import enum
import json
import types
import typing
import uuid
from pathlib import Path
from typing import Any, Literal, Union

from reflex_build_sdk._decode import json_key

OPENAPI_SNAPSHOT = Path(__file__).parents[3] / "packages/reflex-build-sdk/openapi.json"


def load_components() -> dict[str, Any]:
    """Load the schema components of the snapshot.

    Returns:
        The component schemas by name.
    """
    return json.loads(OPENAPI_SNAPSHOT.read_text())["components"]["schemas"]


def _members(schema: dict[str, Any]) -> list[dict[str, Any]]:
    return schema.get("anyOf", [schema])


def _nullable(schema: dict[str, Any]) -> bool:
    return any(member.get("type") == "null" for member in _members(schema))


def _describe(schema: dict[str, Any]) -> str:
    return json.dumps(schema, sort_keys=True)


def type_problems(
    tp: Any,
    schema: dict[str, Any],
    models: dict[type, tuple[str, ...]],
    path: str,
) -> list[str]:
    """Find where a Python type cannot decode the values a schema allows.

    The SDK type may accept more than the schema (e.g. ``str`` for an enum, or an
    optional field the schema never sends as null), but everything the schema
    allows must decode.

    Args:
        tp: The SDK's type annotation.
        schema: The schema of the values.
        models: The schema components each SDK model is checked against.
        path: Where the type appears, for messages.

    Returns:
        A description of each incompatibility.
    """
    if tp is Any:
        return []
    origin = typing.get_origin(tp)
    args = typing.get_args(tp)
    non_null = [member for member in _members(schema) if member.get("type") != "null"]
    if origin is Union or origin is types.UnionType:
        sdk_members = [arg for arg in args if arg is not type(None)]
        if _nullable(schema) and type(None) not in args:
            return [f"{path}: the schema allows null but the SDK type does not"]
        problems = []
        for member in non_null:
            # Each schema alternative must decode into some SDK alternative.
            if all(
                type_problems(sdk_member, member, models, path)
                for sdk_member in sdk_members
            ):
                problems.append(
                    f"{path}: no SDK type accepts schema member {_describe(member)}"
                )
        return problems
    if _nullable(schema):
        return [f"{path}: the schema allows null but the SDK type does not"]
    if len(non_null) != 1:
        if any(type_problems(tp, member, models, path) for member in non_null):
            return [f"{path}: {tp!r} cannot accept every member of {_describe(schema)}"]
        return []
    (schema,) = non_null
    if "$ref" in schema:
        component = schema["$ref"].rsplit("/", 1)[-1]
        if component not in models.get(tp, ()):
            return [f"{path}: expected a model checked against {component}, got {tp!r}"]
        return []
    schema_type = schema.get("type")
    schema_format = schema.get("format")
    if origin is Literal or (isinstance(tp, type) and issubclass(tp, enum.Enum)):
        # Types are compared too, as the decoder does: True == 1, but a JSON true
        # does not decode into the literal 1.
        allowed = {
            (type(value), value)
            for value in (
                args if origin is Literal else [member.value for member in tp]
            )
        }
        values = (
            schema["enum"]
            if "enum" in schema
            else [schema["const"]]
            if "const" in schema
            else None
        )
        if values is None or any(
            (type(value), value) not in allowed for value in values
        ):
            return [
                f"{path}: {tp!r} does not accept every value of {_describe(schema)}"
            ]
        return []
    expected = {
        str: ("string", None),
        uuid.UUID: ("string", "uuid"),
        datetime.datetime: ("string", "date-time"),
        datetime.date: ("string", "date"),
        bool: ("boolean", None),
        int: ("integer", None),
    }
    if tp in expected:
        expected_type, expected_format = expected[tp]
        # A string without a format may still hold UUIDs or datetimes: the backend
        # declares many of its fields with plain types. And ``str`` accepts a string
        # of any format.
        if schema_type != expected_type or (
            expected_format is not None and schema_format not in (None, expected_format)
        ):
            return [f"{path}: {tp!r} does not match {_describe(schema)}"]
        return []
    if tp is float:
        if schema_type not in ("number", "integer"):
            return [f"{path}: float does not match {_describe(schema)}"]
        return []
    if origin is list:
        if schema_type != "array":
            return [f"{path}: list does not match {_describe(schema)}"]
        return type_problems(args[0], schema.get("items", {}), models, f"{path}[]")
    if origin is dict:
        if schema_type != "object":
            return [f"{path}: dict does not match {_describe(schema)}"]
        values = schema.get("additionalProperties", True)
        return (
            []
            if values is True
            else type_problems(args[1], values, models, f"{path}{{}}")
        )
    return [f"{path}: unsupported SDK type {tp!r}"]


def model_problems(
    model: type, component: dict[str, Any], models: dict[type, tuple[str, ...]]
) -> list[str]:
    """Find where a model cannot decode the objects its schema component describes.

    Args:
        model: The SDK dataclass.
        component: The schema component the model is checked against.
        models: The schema components each SDK model is checked against.

    Returns:
        A description of each incompatibility.
    """
    hints = typing.get_type_hints(model)
    properties = component.get("properties", {})
    required = set(component.get("required", []))
    problems = []
    for field in dataclasses.fields(model):
        key = json_key(field)
        path = f"{model.__name__}.{field.name}"
        if key not in properties:
            problems.append(f"{path}: not in the schema")
            continue
        has_default = (
            field.default is not dataclasses.MISSING
            or field.default_factory is not dataclasses.MISSING
        )
        if key not in required and not has_default:
            problems.append(f"{path}: optional in the schema but required by the SDK")
        problems.extend(type_problems(hints[field.name], properties[key], models, path))
    return problems
