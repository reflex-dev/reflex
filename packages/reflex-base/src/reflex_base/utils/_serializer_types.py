"""Optional serializer annotations resolved only when introspected at runtime."""

from importlib import import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pandas import DataFrame as DataFrame
    from PIL.Image import Image as Image
    from plotly.graph_objects import Figure as Figure
    from plotly.graph_objs.layout import Template as Template

_TYPE_MODULES = {
    "DataFrame": "pandas",
    "Image": "PIL.Image",
    "Figure": "plotly.graph_objects",
    "Template": "plotly.graph_objs.layout",
}


def __getattr__(name: str) -> type:
    """Resolve an optional type without importing unused serializer dependencies.

    Args:
        name: The optional type name.

    Returns:
        The concrete type from its optional dependency.

    Raises:
        AttributeError: If the name is not an optional serializer type.
    """
    if name not in _TYPE_MODULES:
        msg = f"module {__name__!r} has no attribute {name!r}"
        raise AttributeError(msg)
    value = getattr(import_module(_TYPE_MODULES[name]), name)
    globals()[name] = value
    return value
