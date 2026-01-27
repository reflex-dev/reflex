"""Compatibility hacks and helpers."""

import sys
from collections.abc import Mapping
from importlib.util import find_spec
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pydantic.fields import FieldInfo


async def windows_hot_reload_lifespan_hack():
    """[REF-3164] A hack to fix hot reload on Windows.

    Uvicorn has an issue stopping itself on Windows after detecting changes in
    the filesystem.

    This workaround repeatedly prints and flushes null characters to stderr,
    which seems to allow the uvicorn server to exit when the CTRL-C signal is
    sent from the reloader process.

    Don't ask me why this works, I discovered it by accident - masenf.
    """
    import asyncio
    import sys

    try:
        while True:
            sys.stderr.write("\0")
            sys.stderr.flush()
            await asyncio.sleep(0.5)
    except asyncio.CancelledError:
        pass


def annotations_from_namespace(namespace: Mapping[str, Any]) -> dict[str, Any]:
    """Get the annotations from a class namespace.

    Args:
        namespace: The class namespace.

    Returns:
        The (forward-ref) annotations from the class namespace.
    """
    if sys.version_info >= (3, 14) and "__annotations__" not in namespace:
        from annotationlib import (
            Format,
            call_annotate_function,
            get_annotate_from_class_namespace,
        )

        if annotate := get_annotate_from_class_namespace(namespace):
            return call_annotate_function(annotate, format=Format.FORWARDREF)
    return namespace.get("__annotations__", {})


if find_spec("pydantic") and find_spec("pydantic.v1"):
    from pydantic.v1.main import ModelMetaclass

    class ModelMetaclassLazyAnnotations(ModelMetaclass):
        """Compatibility metaclass to resolve python3.14 style lazy annotations."""

        def __new__(mcs, name: str, bases: tuple, namespace: dict, **kwargs):
            """Resolve python3.14 style lazy annotations before passing off to pydantic v1.

            Args:
                name: The class name.
                bases: The base classes.
                namespace: The class namespace.
                **kwargs: Additional keyword arguments.

            Returns:
                The created class.
            """
            namespace["__annotations__"] = annotations_from_namespace(namespace)
            return super().__new__(mcs, name, bases, namespace, **kwargs)

else:
    ModelMetaclassLazyAnnotations = type  # type: ignore[assignment]


def sqlmodel_field_has_primary_key(field_info: "FieldInfo") -> bool:
    """Determines if a field is a primary.

    Args:
        field_info: a rx.model field

    Returns:
        If field_info is a primary key (Bool)
    """
    if getattr(field_info, "primary_key", None) is True:
        return True
    if getattr(field_info, "sa_column", None) is None:
        return False
    return bool(getattr(field_info.sa_column, "primary_key", None))  # pyright: ignore[reportAttributeAccessIssue]
