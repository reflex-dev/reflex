"""Decode JSON values into the typed dataclass models of the SDK."""

from __future__ import annotations

import dataclasses
import datetime
import enum
import types
import typing
import uuid
from collections.abc import Callable, Iterable
from typing import Any, Literal, NoReturn, TypeVar, Union

T = TypeVar("T")

# A decoder converts a JSON value or raises DecodeError.
Decoder = Callable[[Any], Any]


class DecodeError(ValueError):
    """A JSON value does not match the type it is decoded into."""

    # What went wrong, without the location.
    message: str
    # Where it went wrong, innermost key or index first: each enclosing container
    # appends its segment while the error propagates, so a successful decode never
    # pays for building a path.
    path: list[str | int]

    def __init__(self, message: str) -> None:
        """Initialize the error.

        Args:
            message: What went wrong, without the location.
        """
        super().__init__(message)
        self.message = message
        self.path = []

    def __str__(self) -> str:
        """Describe the error with its location.

        Returns:
            The message and the JSON path of the offending value.
        """
        return f"{self.message} at {_format_path('$', self.path)}"


def _format_path(root: str, path: list[str | int]) -> str:
    return root + "".join(
        f"[{segment}]" if type(segment) is int else f".{segment}"
        for segment in reversed(path)
    )


_decoders: dict[Any, Decoder] = {}

# The dataclass field metadata key holding the field's name in API responses.
_JSON_NAME = "reflex_build_sdk.json_name"


def json_name(name: str) -> dict[str, str]:
    """Build the field metadata of a model field stored under another key in responses.

    Used as ``dataclasses.field(metadata=json_name("key"))``, which type checkers
    still see as a required field.

    Args:
        name: The key in API responses.

    Returns:
        The metadata to pass to ``dataclasses.field``.
    """
    return {_JSON_NAME: name}


def json_key(field: dataclasses.Field) -> str:
    """Get the key API responses store a model field under.

    Args:
        field: The dataclass field.

    Returns:
        The response key, which is the field name unless declared with ``json_name``.
    """
    return field.metadata.get(_JSON_NAME, field.name)


def decode(tp: type[T], value: Any) -> T:
    """Decode a JSON value into a type.

    Unknown object keys are ignored, so models keep decoding responses from newer
    servers that return more fields.

    Args:
        tp: The type to decode into: a dataclass, a primitive, ``UUID``, ``datetime``,
            ``date``, an ``Enum``, a ``Literal``, or a ``list``, ``dict``, fixed-length
            ``tuple`` or union of those.
        value: The JSON value, as returned by ``json.loads``.

    Returns:
        The decoded value.
    """
    return _decoder_for(tp)(value)


def _decoder_for(tp: Any) -> Decoder:
    decoder = _decoders.get(tp)
    if decoder is None:
        decoder = _decoders[tp] = _build(tp)
    return decoder


def _mismatch(expected: str, value: Any) -> NoReturn:
    msg = f"expected {expected}, got {type(value).__name__}"
    raise DecodeError(msg)


def _decode_any(value: Any) -> Any:
    return value


def _decode_never(value: Any) -> NoReturn:
    _mismatch("no value", value)


def _decode_none(value: Any) -> None:
    if value is not None:
        _mismatch("null", value)


def _decode_str(value: Any) -> str:
    if type(value) is not str:
        _mismatch("string", value)
    return value


def _decode_bool(value: Any) -> bool:
    if type(value) is not bool:
        _mismatch("boolean", value)
    return value


def _decode_int(value: Any) -> int:
    if type(value) is not int:
        _mismatch("integer", value)
    return value


def _decode_float(value: Any) -> float:
    if type(value) is float:
        return value
    if type(value) is int:
        return float(value)
    _mismatch("number", value)


def _type_check(container: type, name: str) -> Decoder:
    def check(value: Any) -> Any:
        if type(value) is not container:
            _mismatch(name, value)
        return value

    return check


def _string_parser(name: str, parse: Callable[[str], Any]) -> Decoder:
    def decode_string(value: Any) -> Any:
        if type(value) is not str:
            _mismatch(name, value)
        try:
            return parse(value)
        except ValueError as ex:
            msg = f"invalid {name} {value!r}"
            raise DecodeError(msg) from ex

    return decode_string


def _parse_datetime(value: str) -> datetime.datetime:
    # fromisoformat only accepts a trailing "Z" from Python 3.11.
    if value.endswith(("Z", "z")):
        value = value[:-1] + "+00:00"
    return datetime.datetime.fromisoformat(value)


_PRIMITIVES: dict[Any, Decoder] = {
    Any: _decode_any,
    object: _decode_any,
    type(None): _decode_none,
    # Matches nothing, so dict[str, NoReturn] only accepts an empty object.
    NoReturn: _decode_never,
    str: _decode_str,
    bool: _decode_bool,
    int: _decode_int,
    float: _decode_float,
    # Unparameterized containers are checked but their items are left as-is.
    list: _type_check(list, "array"),
    dict: _type_check(dict, "object"),
    uuid.UUID: _string_parser("UUID", uuid.UUID),
    datetime.datetime: _string_parser("datetime", _parse_datetime),
    datetime.date: _string_parser("date", datetime.date.fromisoformat),
}


def _build(tp: Any) -> Decoder:
    primitive = _PRIMITIVES.get(tp)
    if primitive is not None:
        return primitive
    origin = typing.get_origin(tp)
    args = typing.get_args(tp)
    if origin is Union or origin is types.UnionType:
        return _build_union(args)
    if origin is Literal:
        return _build_literal(args)
    if origin is list:
        return _build_list(args[0])
    if origin is dict:
        return _build_dict(args[1])
    if origin is tuple:
        return _build_tuple(args)
    if isinstance(tp, type):
        if issubclass(tp, enum.Enum):
            return _build_enum(tp)
        if dataclasses.is_dataclass(tp):
            return _build_dataclass(tp)
    msg = f"cannot decode into {tp!r}"
    raise TypeError(msg)


def _build_union(members: tuple[Any, ...]) -> Decoder:
    optional = type(None) in members
    decoders = [_decoder_for(member) for member in members if member is not type(None)]
    if len(decoders) == 1:
        (only,) = decoders

        def decode_optional(value: Any) -> Any:
            return None if value is None else only(value)

        return decode_optional

    def decode_union(value: Any) -> Any:
        if value is None and optional:
            return None
        errors = []
        for decoder in decoders:
            try:
                return decoder(value)
            except DecodeError as ex:  # noqa: PERF203
                errors.append(
                    f"{ex.message} at {_format_path('', ex.path)}"
                    if ex.path
                    else ex.message
                )
        msg = f"matched no member of the union ({'; '.join(errors)})"
        raise DecodeError(msg)

    return decode_union


def _build_literal(allowed: tuple[Any, ...]) -> Decoder:
    def decode_literal(value: Any) -> Any:
        # Types are compared too: True == 1, but a boolean is not the literal 1.
        if not any(
            type(value) is type(option) and value == option for option in allowed
        ):
            msg = f"expected one of {allowed!r}, got {value!r}"
            raise DecodeError(msg)
        return value

    return decode_literal


def _build_list(item_type: Any) -> Decoder:
    decode_item = _decoder_for(item_type)
    if decode_item is _decode_any:
        return _PRIMITIVES[list]

    def decode_list(value: Any) -> list:
        if type(value) is not list:
            _mismatch("array", value)
        try:
            return [decode_item(item) for item in value]
        except DecodeError as ex:
            # Locating the item again is only paid for on the failure path.
            ex.path.append(_failing_segment(decode_item, enumerate(value)))
            raise

    return decode_list


def _failing_segment(
    decoder: Decoder, entries: Iterable[tuple[str | int, Any]]
) -> str | int:
    for segment, item in entries:
        try:
            decoder(item)
        except DecodeError:  # noqa: PERF203
            return segment
    return "?"


def _build_dict(value_type: Any) -> Decoder:
    decode_value = _decoder_for(value_type)
    if decode_value is _decode_any:
        return _PRIMITIVES[dict]

    def decode_dict(value: Any) -> dict:
        if type(value) is not dict:
            _mismatch("object", value)
        try:
            return {key: decode_value(item) for key, item in value.items()}
        except DecodeError as ex:
            ex.path.append(_failing_segment(decode_value, value.items()))
            raise

    return decode_dict


def _build_tuple(item_types: tuple[Any, ...]) -> Decoder:
    # Fixed-length tuples only: a JSON array with one value per position.
    decoders = [_decoder_for(item_type) for item_type in item_types]
    length = len(decoders)

    def decode_tuple(value: Any) -> tuple:
        if type(value) is not list or len(value) != length:
            _mismatch(f"array of {length}", value)
        index = 0
        items = []
        try:
            for index, decoder in enumerate(decoders):
                items.append(decoder(value[index]))
        except DecodeError as ex:
            ex.path.append(index)
            raise
        return tuple(items)

    return decode_tuple


def _build_enum(tp: type[enum.Enum]) -> Decoder:
    def decode_enum(value: Any) -> enum.Enum:
        try:
            return tp(value)
        except ValueError as ex:
            msg = f"invalid {tp.__name__} {value!r}"
            raise DecodeError(msg) from ex

    return decode_enum


def _build_dataclass(tp: type) -> Decoder:
    # Field types are resolved on first use: resolving them here would recurse
    # forever on a self-referencing model, and resolving the string annotations
    # needs every referenced model to be defined, which import order may not
    # guarantee yet.
    fields: list[tuple[str, str, Decoder, bool]] | None = None

    def resolve_fields() -> list[tuple[str, str, Decoder, bool]]:
        hints = typing.get_type_hints(tp)
        return [
            (
                field.name,
                json_key(field),
                _decoder_for(hints[field.name]),
                field.default is dataclasses.MISSING
                and field.default_factory is dataclasses.MISSING,
            )
            for field in dataclasses.fields(tp)
            if field.init
        ]

    def decode_dataclass(value: Any) -> Any:
        nonlocal fields
        if type(value) is not dict:
            _mismatch(f"{tp.__name__} object", value)
        if fields is None:
            fields = resolve_fields()
        kwargs = {}
        key = ""
        try:
            for name, key, decode_field, required in fields:
                if key in value:
                    kwargs[name] = decode_field(value[key])
                elif required:
                    break
            else:
                return tp(**kwargs)
        except DecodeError as ex:
            ex.path.append(key)
            raise
        msg = f"missing required field {key!r}"
        raise DecodeError(msg)

    return decode_dataclass
