"""Serializers used to convert Var types to JSON strings."""

from __future__ import annotations

import base64
import dataclasses
import decimal
import functools
import inspect
import io
import json
import logging
import os
import sys
import uuid
import warnings
from collections.abc import Callable, Mapping, Sequence
from contextlib import suppress
from datetime import date, datetime, time, timedelta
from enum import Enum
from importlib.util import find_spec
from pathlib import Path
from typing import Any, Literal, TypeVar, get_type_hints, overload
from uuid import UUID

from reflex_base.constants.colors import Color
from reflex_base.utils import _serializer_types, types

logger = logging.getLogger(__name__)

# Mapping from type to a serializer.
# The serializer should convert the type to a JSON object.
SerializedType = str | bool | int | float | list | dict | None


Serializer = Callable[[Any], SerializedType]


SERIALIZERS: dict[type, Serializer] = {}
SERIALIZER_TYPES: dict[type, type] = {}
_OPTIONAL_SERIALIZERS: dict[str, Serializer] = {}
_OPTIONAL_SERIALIZER_TYPES: dict[str, type] = {}
_OPTIONAL_SERIALIZER_MODULES: dict[str, tuple[str, ...]] = {}

SERIALIZED_FUNCTION = TypeVar("SERIALIZED_FUNCTION", bound=Serializer)
_REGISTRY_VALUE = TypeVar("_REGISTRY_VALUE")


deserializers = {
    int: int,
    float: float,
    datetime: datetime.fromisoformat,
    date: date.fromisoformat,
    time: time.fromisoformat,
    uuid.UUID: uuid.UUID,
}


def _get_optional_type_name(type_: type) -> str | None:
    """Identify an optional type by identity in an already-loaded module.

    Args:
        type_: The value type that may belong to an optional dependency.

    Returns:
        The optional type name, or None for an unrelated type.
    """
    name = getattr(type_, "__name__", None)
    if not isinstance(name, str):
        return None
    for module_name in _OPTIONAL_SERIALIZER_MODULES.get(name, ()):
        module = sys.modules.get(module_name)
        if module is not None and vars(module).get(name) is type_:
            return name
    return None


@overload
def serializer(
    fn: None = None,
    to: type[SerializedType] | None = None,
    overwrite: bool | None = None,
) -> Callable[[SERIALIZED_FUNCTION], SERIALIZED_FUNCTION]: ...


@overload
def serializer(
    fn: SERIALIZED_FUNCTION,
    to: type[SerializedType] | None = None,
    overwrite: bool | None = None,
) -> SERIALIZED_FUNCTION: ...


def serializer(
    fn: SERIALIZED_FUNCTION | None = None,
    to: Any = None,
    overwrite: bool | None = None,
) -> SERIALIZED_FUNCTION | Callable[[SERIALIZED_FUNCTION], SERIALIZED_FUNCTION]:
    """Decorator to add a serializer for a given type.

    Args:
        fn: The function to decorate.
        to: The type returned by the serializer. If this is `str`, then any Var created from this type will be treated as a string.
        overwrite: Whether to overwrite the existing serializer.

    Returns:
        The decorated function.
    """

    def wrapper(fn: SERIALIZED_FUNCTION) -> SERIALIZED_FUNCTION:
        # Check the type hints to get the type of the argument.
        type_hints = get_type_hints(fn)
        args = [arg for arg in type_hints if arg != "return"]

        # Make sure the function takes a single argument.
        if len(args) != 1:
            msg = "Serializer must take a single argument."
            raise ValueError(msg)

        # Get the type of the argument.
        type_ = type_hints[args[0]]

        # Make sure the type is not already registered.
        registered_fn = SERIALIZERS.get(type_)
        if registered_fn is None and (name := _get_optional_type_name(type_)):
            registered_fn = _OPTIONAL_SERIALIZERS[name]
        if registered_fn is not None and registered_fn != fn and overwrite is not True:
            message = f"Overwriting serializer for type {type_} from {registered_fn.__module__}:{registered_fn.__qualname__} to {fn.__module__}:{fn.__qualname__}."
            if overwrite is False:
                raise ValueError(message)
            caller_frame = next(
                filter(
                    lambda frame: frame.filename != __file__,
                    inspect.getouterframes(inspect.currentframe()),
                ),
                None,
            )
            file_info = (
                f"(at {caller_frame.filename}:{caller_frame.lineno})"
                if caller_frame
                else ""
            )
            logger.warning(
                f"{message} Call rx.serializer with `overwrite=True` if this is intentional. {file_info}"
            )

        to_type = to or type_hints.get("return")

        # Apply type transformation if requested.
        if to_type:
            SERIALIZER_TYPES[type_] = to_type
            get_serializer_type.cache_clear()

        # Register the serializer.
        SERIALIZERS[type_] = fn
        get_serializer.cache_clear()

        # Return the function.
        return fn

    if fn is not None:
        return wrapper(fn)
    return wrapper


@overload
def serialize(
    value: Any, get_type: Literal[True]
) -> tuple[SerializedType | None, types.GenericType | None]: ...


@overload
def serialize(value: Any, get_type: Literal[False]) -> SerializedType | None: ...


@overload
def serialize(value: Any) -> SerializedType | None: ...


def serialize(
    value: Any, get_type: bool = False
) -> SerializedType | tuple[SerializedType | None, types.GenericType | None] | None:
    """Serialize the value to a JSON string.

    Args:
        value: The value to serialize.
        get_type: Whether to return the type of the serialized value.

    Returns:
        The serialized value, or None if a serializer is not found.
    """
    # Get the serializer for the type.
    serializer = get_serializer(type(value))

    # If there is no serializer, return None.
    if serializer is None:
        if dataclasses.is_dataclass(value) and not isinstance(value, type):
            return {k.name: getattr(value, k.name) for k in dataclasses.fields(value)}

        if get_type:
            return None, None
        return None

    # Serialize the value.
    serialized = serializer(value)

    # Return the serialized value and the type.
    if get_type:
        return serialized, get_serializer_type(type(value))
    return serialized


def _find_serializer(
    type_: type,
    registry: dict[type, _REGISTRY_VALUE],
    optional_defaults: dict[str, _REGISTRY_VALUE],
) -> _REGISTRY_VALUE | None:
    """Resolve defaults and overrides without importing or mutating the registry.

    Args:
        type_: The type to find a serializer for.
        registry: Explicit registrations for functions or output types.
        optional_defaults: Defaults for the corresponding optional types.

    Returns:
        The matching registration, or None if no serializer is registered.
    """
    if (registered := registry.get(type_)) is not None:
        return registered

    best: _REGISTRY_VALUE | None = None
    best_priority = -1
    for base in getattr(type_, "__mro__", ()):
        if name := _get_optional_type_name(base):
            value = registry.get(base, optional_defaults[name])
            if base is type_:
                return value
            priority = _OPTIONAL_SERIALIZER_ORDER[name]
            if priority > best_priority:
                best, best_priority = value, priority

    # A private copy permits concurrent/reentrant registration without a lock
    # around user-defined hash or subclass callbacks, or destructive reordering.
    for registered_type, value in reversed(registry.copy().items()):
        priority = _DEFAULT_SERIALIZER_ORDER.get(id(registered_type))
        if priority is None and (name := _get_optional_type_name(registered_type)):
            priority = _OPTIONAL_SERIALIZER_ORDER[name]
        if (priority is None or priority > best_priority) and issubclass(
            type_, registered_type
        ):
            # User registrations follow all defaults, in reverse insertion order.
            if priority is None:
                return value
            best, best_priority = value, priority
    return best


@functools.lru_cache
def get_serializer(type_: type) -> Serializer | None:
    """Get the serializer for the type.

    Args:
        type_: The type to get the serializer for.

    Returns:
        The serializer for the type, or None if there is no serializer.
    """
    return _find_serializer(type_, SERIALIZERS, _OPTIONAL_SERIALIZERS)


@functools.lru_cache
def get_serializer_type(type_: type) -> type | None:
    """Get the converted type for the type after serializing.

    Args:
        type_: The type to get the serializer type for.

    Returns:
        The serialized type for the type, or None if there is no type conversion registered.
    """
    return _find_serializer(type_, SERIALIZER_TYPES, _OPTIONAL_SERIALIZER_TYPES)


def has_serializer(type_: type, into_type: type | None = None) -> bool:
    """Check if there is a serializer for the type.

    Args:
        type_: The type to check.
        into_type: The type to serialize into.

    Returns:
        Whether there is a serializer for the type.
    """
    serializer_for_type = get_serializer(type_)
    return serializer_for_type is not None and (
        into_type is None or get_serializer_type(type_) == into_type
    )


def can_serialize(type_: type, into_type: type | None = None) -> bool:
    """Check if there is a serializer for the type.

    Args:
        type_: The type to check.
        into_type: The type to serialize into.

    Returns:
        Whether there is a serializer for the type.
    """
    return (
        isinstance(type_, type)
        and dataclasses.is_dataclass(type_)
        and (into_type is None or into_type is dict)
    ) or has_serializer(type_, into_type)


@serializer(to=str)
def serialize_type(value: type) -> str:
    """Serialize a python type.

    Args:
        value: the type to serialize.

    Returns:
        The serialized type.
    """
    return value.__name__


if find_spec("pydantic"):
    from pydantic import BaseModel

    @serializer(to=dict)
    def serialize_base_model(model: BaseModel) -> dict:
        """Serialize a pydantic v2 BaseModel instance.

        Args:
            model: The BaseModel to serialize.

        Returns:
            The serialized BaseModel.
        """
        return model.model_dump()


@serializer
def serialize_set(value: set) -> list:
    """Serialize a set to a JSON serializable list.

    Args:
        value: The set to serialize.

    Returns:
        The serialized list.
    """
    return list(value)


@serializer
def serialize_sequence(value: Sequence) -> list:
    """Serialize a sequence to a JSON serializable list.

    Args:
        value: The sequence to serialize.

    Returns:
        The serialized list.
    """
    return list(value)


@serializer(to=dict)
def serialize_mapping(value: Mapping) -> dict:
    """Serialize a mapping type to a dictionary.

    Args:
        value: The mapping instance to serialize.

    Returns:
        A new dictionary containing the same key-value pairs as the input mapping.
    """
    return {**value}


@serializer(to=str)
def serialize_datetime(dt: date | datetime | time | timedelta) -> str:
    """Serialize a datetime to a JSON string.

    Args:
        dt: The datetime to serialize.

    Returns:
        The serialized datetime.
    """
    return str(dt)


@serializer(to=str)
def serialize_path(path: Path) -> str:
    """Serialize a pathlib.Path to a JSON string.

    Args:
        path: The path to serialize.

    Returns:
        The serialized path.
    """
    return str(path.as_posix())


@serializer
def serialize_enum(en: Enum) -> str:
    """Serialize a enum to a JSON string.

    Args:
        en: The enum to serialize.

    Returns:
        The serialized enum.
    """
    return en.value


@serializer(to=str)
def serialize_uuid(uuid: UUID) -> str:
    """Serialize a UUID to a JSON string.

    Args:
        uuid: The UUID to serialize.

    Returns:
        The serialized UUID.
    """
    return str(uuid)


@serializer(to=float)
def serialize_decimal(value: decimal.Decimal) -> float:
    """Serialize a Decimal to a float.

    Args:
        value: The Decimal to serialize.

    Returns:
        The serialized Decimal as a float.
    """
    return float(value)


@serializer(to=str)
def serialize_color(color: Color) -> str:
    """Serialize a color.

    Args:
        color: The color to serialize.

    Returns:
        The serialized color.
    """
    return color.__format__("")


def format_dataframe_values(df: _serializer_types.DataFrame) -> list[list[Any]]:
    """Format dataframe values to a list of lists.

    Args:
        df: The dataframe to format.

    Returns:
        The dataframe as a list of lists.
    """
    return [
        [str(d) if isinstance(d, (list, tuple)) else d for d in data]
        for data in list(df.to_numpy().tolist())
    ]


def serialize_dataframe(df: _serializer_types.DataFrame) -> dict:
    """Serialize a pandas dataframe.

    Args:
        df: The dataframe to serialize.

    Returns:
        The serialized dataframe.
    """
    return {
        "columns": df.columns.tolist(),
        "data": format_dataframe_values(df),
    }


def serialize_figure(figure: _serializer_types.Figure) -> dict:
    """Serialize a plotly figure.

    Args:
        figure: The figure to serialize.

    Returns:
        The serialized figure.
    """
    from plotly.io import to_json

    return json.loads(str(to_json(figure)))


def serialize_template(template: _serializer_types.Template) -> dict:
    """Serialize a plotly template.

    Args:
        template: The template to serialize.

    Returns:
        The serialized template.
    """
    from plotly.io import to_json

    return {
        "data": json.loads(str(to_json(template.data))),
        "layout": json.loads(str(to_json(template.layout))),
    }


def serialize_image(image: _serializer_types.Image) -> str:
    """Serialize a Pillow image as a data URI.

    Args:
        image: The image to serialize.

    Returns:
        The serialized image.
    """
    from PIL.Image import MIME

    buff = io.BytesIO()
    image_format = getattr(image, "format", None) or "PNG"
    image.save(buff, format=image_format)
    image_bytes = buff.getvalue()
    base64_image = base64.b64encode(image_bytes).decode("utf-8")
    try:
        # Newer method to get the mime type, but does not always work.
        mime_type = image.get_format_mimetype()  # pyright: ignore [reportAttributeAccessIssue]
    except AttributeError:
        try:
            # Fallback method
            mime_type = MIME[image_format]
        except KeyError:
            # Unknown mime_type: warn and return image/png and hope the browser can sort it out.
            warnings.warn(  # noqa: B028
                f"Unknown mime type for {image} {image_format}. Defaulting to image/png"
            )
            mime_type = "image/png"

    return f"data:{mime_type};base64,{base64_image}"


def serialize_sqlmodel(m: _serializer_types.SQLModel) -> dict[str, Any]:
    """Serialize a SQLModel instance, including its loaded relationships.

    Args:
        m: The SQLModel instance to serialize.

    Returns:
        The model fields and available relationships.
    """
    from sqlalchemy.orm.exc import DetachedInstanceError

    fields = m.model_dump()
    relationships = {}
    for name in m.__sqlmodel_relationships__:
        with suppress(DetachedInstanceError):
            relationships[name] = getattr(m, name)
    return {**fields, **relationships}


def _prepare_serializers_for_fork() -> None:
    """Finish Plotly JSON initialization before forking a process using it."""
    for name in ("Figure", "Template"):
        for module_name in _OPTIONAL_SERIALIZER_MODULES[name]:
            module = sys.modules.get(module_name)
            if module is not None and isinstance(vars(module).get(name), type):
                # JSON engines can defer imports until their first invocation.
                # Finish those imports too, without holding a serializer lock.
                with suppress(ImportError):
                    from plotly.io import to_json

                    to_json({"data": []}, validate=False)

                return


_INITIAL_SERIALIZER_TYPES = tuple(SERIALIZERS)
_DEFAULT_SERIALIZER_ORDER = {
    id(type_): index for index, type_ in enumerate(_INITIAL_SERIALIZER_TYPES)
}
_OPTIONAL_SERIALIZERS = {
    "DataFrame": serialize_dataframe,
    "Figure": serialize_figure,
    "Template": serialize_template,
    "Image": serialize_image,
    "SQLModel": serialize_sqlmodel,
}
_OPTIONAL_SERIALIZER_TYPES = {
    "DataFrame": dict,
    "Figure": dict,
    "Template": dict,
    "Image": str,
    "SQLModel": dict[str, Any],
}
_OPTIONAL_SERIALIZER_MODULES = {
    "DataFrame": ("pandas", "pandas.core.frame"),
    "Figure": ("plotly.graph_objs._figure",),
    "Template": ("plotly.graph_objs.layout._template",),
    "Image": ("PIL.Image",),
    "SQLModel": ("sqlmodel.main",),
}
_OPTIONAL_SERIALIZER_ORDER = {
    name: len(_INITIAL_SERIALIZER_TYPES) + index
    for index, name in enumerate(_OPTIONAL_SERIALIZERS)
}

if hasattr(os, "register_at_fork"):
    os.register_at_fork(before=_prepare_serializers_for_fork)
