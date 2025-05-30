"""Shared field infrastructure for components and props."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import _MISSING_TYPE, MISSING
from typing import Annotated, Any, Generic, TypeVar, get_origin

FIELD_TYPE = TypeVar("FIELD_TYPE")


class BaseField(Generic[FIELD_TYPE]):
    """Base field class used by internal metadata classes."""

    def __init__(
        self,
        default: FIELD_TYPE | _MISSING_TYPE = MISSING,
        default_factory: Callable[[], FIELD_TYPE] | None = None,
        annotated_type: type[Any] | _MISSING_TYPE = MISSING,
    ) -> None:
        """Initialize the field.

        Args:
            default: The default value for the field.
            default_factory: The default factory for the field.
            annotated_type: The annotated type for the field.
        """
        self.default = default
        self.default_factory = default_factory
        self.outer_type_ = self.annotated_type = annotated_type

        # Process type annotation
        type_origin = get_origin(annotated_type) or annotated_type
        if type_origin is Annotated:
            type_origin = annotated_type.__origin__  # pyright: ignore [reportAttributeAccessIssue]
            # For Annotated types, use the actual type inside the annotation
            self.type_ = annotated_type
        else:
            # For other types (including Union), preserve the original type
            self.type_ = annotated_type
        self.type_origin = type_origin

    def default_value(self) -> FIELD_TYPE:
        """Get the default value for the field.

        Returns:
            The default value for the field.

        Raises:
            ValueError: If no default value or factory is provided.
        """
        if self.default is not MISSING:
            return self.default
        if self.default_factory is not None:
            return self.default_factory()
        msg = "No default value or factory provided."
        raise ValueError(msg)
