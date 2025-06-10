"""A class that holds props to be passed or applied to a component."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import _MISSING_TYPE, MISSING
from typing import Any, TypeVar, get_args, get_origin

from typing_extensions import dataclass_transform

from reflex.components.field import BaseField, FieldBasedMeta
from reflex.utils import format
from reflex.utils.exceptions import InvalidPropValueError
from reflex.utils.serializers import serializer
from reflex.utils.types import is_union
from reflex.vars.object import LiteralObjectVar

PROPS_FIELD_TYPE = TypeVar("PROPS_FIELD_TYPE")


def _get_props_subclass(field_type: Any) -> type | None:
    """Extract the Props subclass from a field type annotation.

    Args:
        field_type: The type annotation to check.

    Returns:
        The Props subclass if found, None otherwise.
    """
    from reflex.utils.types import typehint_issubclass

    # For direct class types, we can return them directly if they're Props subclasses
    if isinstance(field_type, type):
        return field_type if typehint_issubclass(field_type, PropsBase) else None

    # For Union types, check each union member
    if is_union(field_type):
        for arg in get_args(field_type):
            result = _get_props_subclass(arg)
            if result is not None:
                return result

    return None


def _find_props_in_list_annotation(field_type: Any) -> type | None:
    """Find Props subclass within a list type annotation.

    Args:
        field_type: The type annotation to check (e.g., list[SomeProps] or list[SomeProps] | None).

    Returns:
        The Props subclass if found in a list annotation, None otherwise.
    """
    origin = get_origin(field_type)
    if origin is list:
        args = get_args(field_type)
        if args:
            return _get_props_subclass(args[0])

    # Handle Union types - check if any union member is a list
    if is_union(field_type):
        for arg in get_args(field_type):
            if arg is not type(None):  # Skip None from Optional
                list_element = _find_props_in_list_annotation(arg)
                if list_element is not None:
                    return list_element

    return None


class PropsField(BaseField[PROPS_FIELD_TYPE]):
    """A field for a props class."""

    def __init__(
        self,
        default: PROPS_FIELD_TYPE | _MISSING_TYPE = MISSING,
        default_factory: Callable[[], PROPS_FIELD_TYPE] | None = None,
        annotated_type: type[Any] | _MISSING_TYPE = MISSING,
    ) -> None:
        """Initialize the field.

        Args:
            default: The default value for the field.
            default_factory: The default factory for the field.
            annotated_type: The annotated type for the field.
        """
        super().__init__(default, default_factory, annotated_type)
        self._name: str = ""  # Will be set by metaclass

    @property
    def required(self) -> bool:
        """Check if the field is required (for Pydantic compatibility).

        Returns:
            True if the field has no default value or factory.
        """
        return self.default is MISSING and self.default_factory is None

    @property
    def name(self) -> str | None:
        """Field name (for Pydantic compatibility).

        Note: This is set by the metaclass when processing fields.

        Returns:
            The field name if set, None otherwise.
        """
        return getattr(self, "_name", None)

    def get_default(self) -> Any:
        """Get the default value (for Pydantic compatibility).

        Returns:
            The default value for the field, or None if required.
        """
        try:
            return self.default_value()
        except ValueError:
            # Field is required (no default)
            return None

    def __repr__(self) -> str:
        """Represent the field in a readable format.

        Returns:
            The string representation of the field.
        """
        annotated_type_str = (
            f", annotated_type={self.annotated_type!r}"
            if self.annotated_type is not MISSING
            else ""
        )
        if self.default is not MISSING:
            return f"PropsField(default={self.default!r}{annotated_type_str})"
        return (
            f"PropsField(default_factory={self.default_factory!r}{annotated_type_str})"
        )


def props_field(
    default: PROPS_FIELD_TYPE | _MISSING_TYPE = MISSING,
    default_factory: Callable[[], PROPS_FIELD_TYPE] | None = None,
) -> PROPS_FIELD_TYPE:
    """Create a field for a props class.

    Args:
        default: The default value for the field.
        default_factory: The default factory for the field.

    Returns:
        The field for the props class.

    Raises:
        ValueError: If both default and default_factory are specified.
    """
    if default is not MISSING and default_factory is not None:
        msg = "cannot specify both default and default_factory"
        raise ValueError(msg)
    return PropsField(  # pyright: ignore [reportReturnType]
        default=default,
        default_factory=default_factory,
        annotated_type=MISSING,
    )


@dataclass_transform(field_specifiers=(props_field,))
class PropsBaseMeta(FieldBasedMeta):
    """Meta class for PropsBase."""

    @classmethod
    def _process_annotated_fields(
        cls,
        namespace: dict[str, Any],
        annotations: dict[str, Any],
        inherited_fields: dict[str, PropsField],
    ) -> dict[str, PropsField]:
        own_fields: dict[str, PropsField] = {}

        for key, annotation in annotations.items():
            value = namespace.get(key, MISSING)

            if value is MISSING:
                # Field with only annotation, no default value
                field = PropsField(annotated_type=annotation, default=None)
            elif not isinstance(value, PropsField):
                # Field with default value
                field = PropsField(annotated_type=annotation, default=value)
            else:
                # Field is already a PropsField, update annotation
                field = PropsField(
                    annotated_type=annotation,
                    default=value.default,
                    default_factory=value.default_factory,
                )

            own_fields[key] = field

        return own_fields

    @classmethod
    def _create_field(
        cls,
        annotated_type: Any,
        default: Any = MISSING,
        default_factory: Callable[[], Any] | None = None,
    ) -> PropsField:
        return PropsField(
            annotated_type=annotated_type,
            default=default,
            default_factory=default_factory,
        )

    @classmethod
    def _finalize_fields(
        cls,
        namespace: dict[str, Any],
        inherited_fields: dict[str, PropsField],
        own_fields: dict[str, PropsField],
    ) -> None:
        # Call parent implementation
        super()._finalize_fields(namespace, inherited_fields, own_fields)

        # Add Pydantic compatibility
        namespace["__fields__"] = namespace["_fields"]


class PropsBase(metaclass=PropsBaseMeta):
    """Base for a class containing props that can be serialized as a JS object."""

    def __init__(self, **kwargs):
        """Initialize the props with field values.

        Args:
            **kwargs: The field values to set.
        """
        # Set field values from kwargs with nested object instantiation
        for key, value in kwargs.items():
            field_info = self.get_fields().get(key)
            if field_info:
                field_type = field_info.annotated_type

                # Check if this field expects a specific Props type and we got a dict
                if isinstance(value, dict):
                    props_class = _get_props_subclass(field_type)
                    if props_class is not None:
                        value = props_class(**value)

                # Check if this field expects a list of Props and we got a list of dicts
                elif isinstance(value, list):
                    element_type = _find_props_in_list_annotation(field_type)
                    if element_type is not None:
                        # Convert each dict in the list to the appropriate Props class
                        value = [
                            element_type(**item) if isinstance(item, dict) else item
                            for item in value
                        ]

            setattr(self, key, value)

        # Set default values for fields not provided
        for field_name, field in self.get_fields().items():
            if field_name not in kwargs:
                if field.default is not MISSING:
                    setattr(self, field_name, field.default)
                elif field.default_factory is not None:
                    setattr(self, field_name, field.default_factory())
                # Note: Fields with no default and no factory remain unset (required fields)

    @classmethod
    def get_fields(cls) -> dict[str, Any]:
        """Get the fields of the object.

        Returns:
            The fields of the object.
        """
        return getattr(cls, "_fields", {})

    def json(self) -> str:
        """Convert the object to a json-like string.

        Vars will be unwrapped so they can represent actual JS var names and functions.

        Keys will be converted to camelCase.

        Returns:
            The object as a Javascript Object literal.
        """
        return LiteralObjectVar.create(
            {format.to_camel_case(key): value for key, value in self.dict().items()}
        ).json()

    def dict(
        self,
        exclude_none: bool = True,
        include: set[str] | None = None,
        exclude: set[str] | None = None,
        **kwargs,
    ):
        """Convert the object to a dictionary.

        Keys will be converted to camelCase.
        By default, None values are excluded (exclude_none=True).

        Args:
            exclude_none: Whether to exclude None values.
            include: Fields to include in the output.
            exclude: Fields to exclude from the output.
            **kwargs: Additional keyword arguments (for compatibility).

        Returns:
            The object as a dictionary.
        """
        result = {}

        for field_name in self.get_fields():
            if hasattr(self, field_name):
                value = getattr(self, field_name)

                # Apply include/exclude filters
                if include is not None and field_name not in include:
                    continue
                if exclude is not None and field_name in exclude:
                    continue

                # Apply exclude_none logic
                if exclude_none and value is None:
                    continue

                # Recursively convert nested structures
                value = self._convert_to_camel_case(
                    value, exclude_none, include, exclude
                )

                # Convert key to camelCase
                camel_key = format.to_camel_case(field_name)
                result[camel_key] = value

        return result

    def _convert_to_camel_case(
        self,
        value: Any,
        exclude_none: bool = True,
        include: set[str] | None = None,
        exclude: set[str] | None = None,
    ) -> Any:
        """Recursively convert nested dictionaries and lists to camelCase.

        Args:
            value: The value to convert.
            exclude_none: Whether to exclude None values.
            include: Fields to include in the output.
            exclude: Fields to exclude from the output.

        Returns:
            The converted value with camelCase keys.
        """
        if isinstance(value, PropsBase):
            # Convert nested PropsBase objects
            return value.dict(
                exclude_none=exclude_none, include=include, exclude=exclude
            )
        if isinstance(value, dict):
            # Convert dictionary keys to camelCase
            return {
                format.to_camel_case(k): self._convert_to_camel_case(
                    v, exclude_none, include, exclude
                )
                for k, v in value.items()
                if not (exclude_none and v is None)
            }
        if isinstance(value, (list, tuple)):
            # Convert list/tuple items recursively
            return [
                self._convert_to_camel_case(item, exclude_none, include, exclude)
                for item in value
            ]
        # Return primitive values as-is
        return value


@serializer(to=dict)
def serialize_props_base(value: PropsBase) -> dict:
    """Serialize a PropsBase instance.

    Unlike serialize_base, this preserves callables (lambdas) since they're
    needed for AG Grid and other components that process them on the frontend.

    Args:
        value: The PropsBase instance to serialize.

    Returns:
        Dictionary representation of the PropsBase instance.
    """
    return value.dict()


class NoExtrasAllowedProps(PropsBase):
    """A class that holds props to be passed or applied to a component with no extra props allowed."""

    def __init__(self, component_name: str | None = None, **kwargs):
        """Initialize the props with validation.

        Args:
            component_name: The custom name of the component.
            kwargs: Kwargs to initialize the props.

        Raises:
            InvalidPropValueError: If invalid props are passed on instantiation.
        """
        component_name = component_name or type(self).__name__

        # Validate fields BEFORE setting them
        known_fields = set(self.__class__.get_fields().keys())
        provided_fields = set(kwargs.keys())
        invalid_fields = provided_fields - known_fields

        if invalid_fields:
            invalid_fields_str = ", ".join(invalid_fields)
            supported_props_str = ", ".join(f'"{field}"' for field in known_fields)
            msg = f"Invalid prop(s) {invalid_fields_str} for {component_name!r}. Supported props are {supported_props_str}"
            raise InvalidPropValueError(msg)

        # Use parent class initialization after validation
        super().__init__(**kwargs)
