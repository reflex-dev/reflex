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


class FieldBasedMeta(type):
    """Shared metaclass for field-based classes like components and props.

    Provides common field inheritance and processing logic for both
    PropsBaseMeta and BaseComponentMeta.
    """

    def __new__(cls, name: str, bases: tuple[type], namespace: dict[str, Any]) -> type:
        """Create a new field-based class.

        Args:
            name: The name of the class.
            bases: The base classes.
            namespace: The class namespace.

        Returns:
            The new class.
        """
        # Collect inherited fields from base classes
        inherited_fields = cls._collect_inherited_fields(bases)

        # Get annotations from the namespace
        annotations = cls._resolve_annotations(namespace, name)

        # Process field overrides (fields with values but no annotations)
        own_fields = cls._process_field_overrides(
            namespace, annotations, inherited_fields
        )

        # Process annotated fields
        own_fields.update(
            cls._process_annotated_fields(namespace, annotations, inherited_fields)
        )

        # Finalize fields and store on class
        cls._finalize_fields(namespace, inherited_fields, own_fields)

        return super().__new__(cls, name, bases, namespace)

    @classmethod
    def _collect_inherited_fields(cls, bases: tuple[type]) -> dict[str, Any]:
        inherited_fields: dict[str, Any] = {}

        # Collect inherited fields from base classes
        for base in bases[::-1]:
            if hasattr(base, "_inherited_fields"):
                inherited_fields.update(base._inherited_fields)
        for base in bases[::-1]:
            if hasattr(base, "_own_fields"):
                inherited_fields.update(base._own_fields)

        return inherited_fields

    @classmethod
    def _resolve_annotations(
        cls, namespace: dict[str, Any], name: str
    ) -> dict[str, Any]:
        return namespace.get("__annotations__", {})

    @classmethod
    def _process_field_overrides(
        cls,
        namespace: dict[str, Any],
        annotations: dict[str, Any],
        inherited_fields: dict[str, Any],
    ) -> dict[str, Any]:
        own_fields: dict[str, Any] = {}

        for key, value in namespace.items():
            if key not in annotations and key in inherited_fields:
                inherited_field = inherited_fields[key]
                new_field = cls._create_field(
                    annotated_type=inherited_field.annotated_type,
                    default=value,
                    default_factory=None,
                )
                own_fields[key] = new_field

        return own_fields

    @classmethod
    def _process_annotated_fields(
        cls,
        namespace: dict[str, Any],
        annotations: dict[str, Any],
        inherited_fields: dict[str, Any],
    ) -> dict[str, Any]:
        raise NotImplementedError

    @classmethod
    def _create_field(
        cls,
        annotated_type: Any,
        default: Any = MISSING,
        default_factory: Callable[[], Any] | None = None,
    ) -> Any:
        raise NotImplementedError

    @classmethod
    def _finalize_fields(
        cls,
        namespace: dict[str, Any],
        inherited_fields: dict[str, Any],
        own_fields: dict[str, Any],
    ) -> None:
        # Combine all fields
        all_fields = inherited_fields | own_fields

        # Set field names for compatibility
        for field_name, field in all_fields.items():
            field._name = field_name

        # Store field mappings on the class
        namespace["_own_fields"] = own_fields
        namespace["_inherited_fields"] = inherited_fields
        namespace["_fields"] = all_fields
