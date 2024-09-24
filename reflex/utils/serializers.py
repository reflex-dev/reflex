"""Serializers used to convert Var types to JSON strings."""

from __future__ import annotations

import dataclasses
import functools
import json
import warnings
from datetime import date, datetime, time, timedelta
from enum import Enum
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Literal,
    Optional,
    Set,
    Tuple,
    Type,
    Union,
    get_type_hints,
    overload,
)

from reflex.base import Base
from reflex.constants.colors import Color, format_color
from reflex.utils import types

# Mapping from type to a serializer.
# The serializer should convert the type to a JSON object.
SerializedType = Union[str, bool, int, float, list, dict, None]


Serializer = Callable[[Type], SerializedType]


SERIALIZERS: dict[Type, Serializer] = {}
SERIALIZER_TYPES: dict[Type, Type] = {}


def serializer(
    fn: Serializer | None = None,
    to: Type | None = None,
) -> Serializer:
    """Decorator to add a serializer for a given type.

    Args:
        fn: The function to decorate.
        to: The type returned by the serializer. If this is `str`, then any Var created from this type will be treated as a string.

    Returns:
        The decorated function.

    Raises:
        ValueError: If the function does not take a single argument.
    """
    if fn is None:
        # If the function is not provided, return a partial that acts as a decorator.
        return functools.partial(serializer, to=to)  # type: ignore

    # Check the type hints to get the type of the argument.
    type_hints = get_type_hints(fn)
    args = [arg for arg in type_hints if arg != "return"]

    # Make sure the function takes a single argument.
    if len(args) != 1:
        raise ValueError("Serializer must take a single argument.")

    # Get the type of the argument.
    type_ = type_hints[args[0]]

    # Make sure the type is not already registered.
    registered_fn = SERIALIZERS.get(type_)
    if registered_fn is not None and registered_fn != fn:
        raise ValueError(
            f"Serializer for type {type_} is already registered as {registered_fn.__qualname__}."
        )

    # Apply type transformation if requested
    if to is not None:
        SERIALIZER_TYPES[type_] = to
        get_serializer_type.cache_clear()

    # Register the serializer.
    SERIALIZERS[type_] = fn
    get_serializer.cache_clear()

    # Return the function.
    return fn


@overload
def serialize(
    value: Any, get_type: Literal[True]
) -> Tuple[Optional[SerializedType], Optional[types.GenericType]]: ...


@overload
def serialize(value: Any, get_type: Literal[False]) -> Optional[SerializedType]: ...


@overload
def serialize(value: Any) -> Optional[SerializedType]: ...


def serialize(
    value: Any, get_type: bool = False
) -> Union[
    Optional[SerializedType],
    Tuple[Optional[SerializedType], Optional[types.GenericType]],
]:
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
            return serialize(dataclasses.asdict(value))
        if get_type:
            return None, None
        return None

    # Serialize the value.
    serialized = serializer(value)

    # Return the serialized value and the type.
    if get_type:
        return serialized, get_serializer_type(type(value))
    else:
        return serialized


@functools.lru_cache
def get_serializer(type_: Type) -> Optional[Serializer]:
    """Get the serializer for the type.

    Args:
        type_: The type to get the serializer for.

    Returns:
        The serializer for the type, or None if there is no serializer.
    """
    # First, check if the type is registered.
    serializer = SERIALIZERS.get(type_)
    if serializer is not None:
        return serializer

    # If the type is not registered, check if it is a subclass of a registered type.
    for registered_type, serializer in reversed(SERIALIZERS.items()):
        if types._issubclass(type_, registered_type):
            return serializer

    # If there is no serializer, return None.
    return None


@functools.lru_cache
def get_serializer_type(type_: Type) -> Optional[Type]:
    """Get the converted type for the type after serializing.

    Args:
        type_: The type to get the serializer type for.

    Returns:
        The serialized type for the type, or None if there is no type conversion registered.
    """
    # First, check if the type is registered.
    serializer = SERIALIZER_TYPES.get(type_)
    if serializer is not None:
        return serializer

    # If the type is not registered, check if it is a subclass of a registered type.
    for registered_type, serializer in reversed(SERIALIZER_TYPES.items()):
        if types._issubclass(type_, registered_type):
            return serializer

    # If there is no serializer, return None.
    return None


def has_serializer(type_: Type) -> bool:
    """Check if there is a serializer for the type.

    Args:
        type_: The type to check.

    Returns:
        Whether there is a serializer for the type.
    """
    return get_serializer(type_) is not None


@serializer(to=str)
def serialize_type(value: type) -> str:
    """Serialize a python type.

    Args:
        value: the type to serialize.

    Returns:
        The serialized type.
    """
    return value.__name__


@serializer
def serialize_str(value: str) -> str:
    """Serialize a string.

    Args:
        value: The string to serialize.

    Returns:
        The serialized string.
    """
    return value


@serializer
def serialize_primitive(value: Union[bool, int, float, None]):
    """Serialize a primitive type.

    Args:
        value: The number/bool/None to serialize.

    Returns:
        The serialized number/bool/None.
    """
    return value


@serializer
def serialize_base(value: Base) -> dict:
    """Serialize a Base instance.

    Args:
        value : The Base to serialize.

    Returns:
        The serialized Base.
    """
    return {k: serialize(v) for k, v in value.dict().items() if not callable(v)}


@serializer
def serialize_list(value: Union[List, Tuple, Set]) -> list:
    """Serialize a list to a JSON string.

    Args:
        value: The list to serialize.

    Returns:
        The serialized list.
    """
    return [serialize(item) for item in value]


@serializer
def serialize_dict(prop: Dict[str, Any]) -> dict:
    """Serialize a dictionary to a JSON string.

    Args:
        prop: The dictionary to serialize.

    Returns:
        The serialized dictionary.
    """
    return {k: serialize(v) for k, v in prop.items()}


@serializer(to=str)
def serialize_datetime(dt: Union[date, datetime, time, timedelta]) -> str:
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
def serialize_color(color: Color) -> str:
    """Serialize a color.

    Args:
        color: The color to serialize.

    Returns:
        The serialized color.
    """
    return format_color(color.color, color.shade, color.alpha)


try:
    from pandas import DataFrame

    def format_dataframe_values(df: DataFrame) -> List[List[Any]]:
        """Format dataframe values to a list of lists.

        Args:
            df: The dataframe to format.

        Returns:
            The dataframe as a list of lists.
        """
        return [
            [str(d) if isinstance(d, (list, tuple)) else d for d in data]
            for data in list(df.values.tolist())
        ]

    @serializer
    def serialize_dataframe(df: DataFrame) -> dict:
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

except ImportError:
    pass

try:
    from plotly.graph_objects import Figure, layout
    from plotly.io import to_json

    @serializer
    def serialize_figure(figure: Figure) -> dict:
        """Serialize a plotly figure.

        Args:
            figure: The figure to serialize.

        Returns:
            The serialized figure.
        """
        return json.loads(str(to_json(figure)))

    @serializer
    def serialize_template(template: layout.Template) -> dict:
        """Serialize a plotly template.

        Args:
            template: The template to serialize.

        Returns:
            The serialized template.
        """
        return {
            "data": json.loads(str(to_json(template.data))),
            "layout": json.loads(str(to_json(template.layout))),
        }

except ImportError:
    pass


try:
    import base64
    import io

    from PIL.Image import MIME
    from PIL.Image import Image as Img

    @serializer
    def serialize_image(image: Img) -> str:
        """Serialize a plotly figure.

        Args:
            image: The image to serialize.

        Returns:
            The serialized image.
        """
        buff = io.BytesIO()
        image_format = getattr(image, "format", None) or "PNG"
        image.save(buff, format=image_format)
        image_bytes = buff.getvalue()
        base64_image = base64.b64encode(image_bytes).decode("utf-8")
        try:
            # Newer method to get the mime type, but does not always work.
            mime_type = image.get_format_mimetype()  # type: ignore
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

except ImportError:
    pass
