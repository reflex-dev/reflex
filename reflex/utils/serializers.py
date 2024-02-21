"""Serializers used to convert Var types to JSON strings."""

from __future__ import annotations

import json
import types as builtin_types
import warnings
from datetime import date, datetime, time, timedelta
from typing import Any, Callable, Dict, List, Set, Tuple, Type, Union, get_type_hints

from reflex.base import Base
from reflex.constants.colors import Color, format_color
from reflex.utils import exceptions, format, types

# Mapping from type to a serializer.
# The serializer should convert the type to a JSON object.
SerializedType = Union[str, bool, int, float, list, dict]
Serializer = Callable[[Type], SerializedType]
SERIALIZERS: dict[Type, Serializer] = {}


def serializer(fn: Serializer) -> Serializer:
    """Decorator to add a serializer for a given type.

    Args:
        fn: The function to decorate.

    Returns:
        The decorated function.

    Raises:
        ValueError: If the function does not take a single argument.
    """
    # Get the global serializers.
    global SERIALIZERS

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

    # Register the serializer.
    SERIALIZERS[type_] = fn

    # Return the function.
    return fn


def serialize(value: Any) -> SerializedType | None:
    """Serialize the value to a JSON string.

    Args:
        value: The value to serialize.

    Returns:
        The serialized value, or None if a serializer is not found.
    """
    # Get the serializer for the type.
    serializer = get_serializer(type(value))

    # If there is no serializer, return None.
    if serializer is None:
        return None

    # Serialize the value.
    return serializer(value)


def get_serializer(type_: Type) -> Serializer | None:
    """Get the serializer for the type.

    Args:
        type_: The type to get the serializer for.

    Returns:
        The serializer for the type, or None if there is no serializer.
    """
    global SERIALIZERS

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


def has_serializer(type_: Type) -> bool:
    """Check if there is a serializer for the type.

    Args:
        type_: The type to check.

    Returns:
        Whether there is a serializer for the type.
    """
    return get_serializer(type_) is not None


@serializer
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
def serialize_primitive(value: Union[bool, int, float, None]) -> str:
    """Serialize a primitive type.

    Args:
        value: The number/bool/None to serialize.

    Returns:
        The serialized number/bool/None.
    """
    return format.json_dumps(value)


@serializer
def serialize_base(value: Base) -> str:
    """Serialize a Base instance.

    Args:
        value : The Base to serialize.

    Returns:
        The serialized Base.
    """
    return value.json()


@serializer
def serialize_list(value: Union[List, Tuple, Set]) -> str:
    """Serialize a list to a JSON string.

    Args:
        value: The list to serialize.

    Returns:
        The serialized list.
    """
    # Dump the list to a string.
    fprop = format.json_dumps(list(value))

    # Unwrap var values.
    return format.unwrap_vars(fprop)


@serializer
def serialize_dict(prop: Dict[str, Any]) -> str:
    """Serialize a dictionary to a JSON string.

    Args:
        prop: The dictionary to serialize.

    Returns:
        The serialized dictionary.

    Raises:
        InvalidStylePropError: If the style prop is invalid.
    """
    # Import here to avoid circular imports.
    from reflex.event import EventHandler

    prop_dict = {}

    for key, value in prop.items():
        if types._issubclass(type(value), Callable):
            raise exceptions.InvalidStylePropError(
                f"The style prop `{format.to_snake_case(key)}` cannot have "  # type: ignore
                f"`{value.fn.__qualname__ if isinstance(value, EventHandler) else value.__qualname__ if isinstance(value, builtin_types.FunctionType) else value}`, "
                f"an event handler or callable as its value"
            )
        prop_dict[key] = value

    # Dump the dict to a string.
    fprop = format.json_dumps(prop_dict)

    # Unwrap var values.
    return format.unwrap_vars(fprop)


@serializer
def serialize_datetime(dt: Union[date, datetime, time, timedelta]) -> str:
    """Serialize a datetime to a JSON string.

    Args:
        dt: The datetime to serialize.

    Returns:
        The serialized datetime.
    """
    return str(dt)


@serializer
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
    from plotly.graph_objects import Figure
    from plotly.io import to_json

    @serializer
    def serialize_figure(figure: Figure) -> list:
        """Serialize a plotly figure.

        Args:
            figure: The figure to serialize.

        Returns:
            The serialized figure.
        """
        return json.loads(str(to_json(figure)))["data"]

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
                warnings.warn(
                    f"Unknown mime type for {image} {image_format}. Defaulting to image/png"
                )
                mime_type = "image/png"

        return f"data:{mime_type};base64,{base64_image}"

except ImportError:
    pass
