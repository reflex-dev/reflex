"""A class that holds props to be passed or applied to a component."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import _MISSING_TYPE, MISSING
from typing import Annotated, Any, Generic, TypeVar, get_args, get_origin

from typing_extensions import dataclass_transform

from reflex.utils import format
from reflex.utils.exceptions import InvalidPropValueError
from reflex.vars.object import LiteralObjectVar

PROPS_FIELD_TYPE = TypeVar("PROPS_FIELD_TYPE")


def _get_list_element_type(field_type: Any) -> type | None:
    """Extract the element type from a list type annotation.

    Args:
        field_type: The type annotation to check (e.g., list[SomeClass] or list[SomeClass] | None).

    Returns:
        The element type if it's a list of Props, None otherwise.
    """
    origin = get_origin(field_type)
    if origin is list:
        args = get_args(field_type)
        if args:
            return _is_props_subclass(args[0])

    # Handle Union types - check if any union member is a list
    if origin is not None and hasattr(field_type, "__args__"):
        for arg in get_args(field_type):
            if arg is not type(None):  # Skip None from Optional
                list_element = _get_list_element_type(arg)
                if list_element is not None:
                    return list_element

    # Handle Python 3.10+ Union syntax (X | Y) - types.UnionType
    import types

    if hasattr(types, "UnionType") and isinstance(field_type, types.UnionType):
        for arg in get_args(field_type):
            if arg is not type(None):  # Skip None from Optional
                list_element = _get_list_element_type(arg)
                if list_element is not None:
                    return list_element

    return None


def _is_props_subclass(field_type: Any) -> type | None:
    """Check if a field type is a subclass of NoExtrasAllowedProps or PropsBase.

    Handles Union types by checking if any of the union members are Props subclasses.

    Args:
        field_type: The type annotation to check.

    Returns:
        The Props subclass if found, None otherwise.
    """
    # Handle direct class types
    if isinstance(field_type, type):
        try:
            # Import here to avoid circular imports
            if hasattr(field_type, "__mro__"):
                # Check if it's a subclass of NoExtrasAllowedProps or PropsBase
                for base in field_type.__mro__:
                    if base.__name__ in ("NoExtrasAllowedProps", "PropsBase"):
                        return field_type
        except (TypeError, AttributeError):
            pass

    # Handle Union types (including Optional which is Union[T, None])
    origin = get_origin(field_type)
    if origin is not None and hasattr(field_type, "__args__"):
        # For Union types, check each argument
        for arg in get_args(field_type):
            if arg is not type(None):  # Skip None from Optional
                result = _is_props_subclass(arg)
                if result is not None:
                    return result

    # Handle Python 3.10+ Union syntax (X | Y) - types.UnionType
    import types

    if hasattr(types, "UnionType") and isinstance(field_type, types.UnionType):
        # For new union syntax, check each argument
        for arg in get_args(field_type):
            if arg is not type(None):  # Skip None from Optional
                result = _is_props_subclass(arg)
                if result is not None:
                    return result

    return None


class PropsField(Generic[PROPS_FIELD_TYPE]):
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
        self.default = default
        self.default_factory = default_factory
        self.outer_type_ = self.annotated_type = annotated_type
        self._name: str = ""  # Will be set by metaclass

        # Process type annotation similar to ComponentField
        type_origin = get_origin(annotated_type) or annotated_type
        if type_origin is Annotated:
            type_origin = annotated_type.__origin__  # pyright: ignore [reportAttributeAccessIssue]
            # For Annotated types, use the actual type inside the annotation
            self.type_ = annotated_type
        else:
            # For other types (including Union), preserve the original type
            self.type_ = annotated_type
        self.type_origin = type_origin

    def default_value(self) -> PROPS_FIELD_TYPE:
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
        default=default, default_factory=default_factory, annotated_type=MISSING
    )


@dataclass_transform(field_specifiers=(props_field,))
class PropsBaseMeta(type):
    """Meta class for PropsBase."""

    def __new__(cls, name: str, bases: tuple[type], namespace: dict[str, Any]) -> type:
        """Create a new class.

        Args:
            name: The name of the class.
            bases: The bases of the class.
            namespace: The namespace of the class.

        Returns:
            The new class.
        """
        # Process field annotations similar to BaseComponentMeta
        inherited_fields: dict[str, PropsField] = {}
        own_fields: dict[str, PropsField] = {}

        # Get annotations from the namespace
        resolved_annotations = namespace.get("__annotations__", {})

        # Collect inherited fields from base classes
        for base in bases[::-1]:
            if hasattr(base, "_inherited_fields"):
                inherited_fields.update(base._inherited_fields)
        for base in bases[::-1]:
            if hasattr(base, "_own_fields"):
                inherited_fields.update(base._own_fields)

        # Process fields with values but no annotations (inherited field overrides)
        for key, value in namespace.items():
            if key not in resolved_annotations and key in inherited_fields:
                inherited_field = inherited_fields[key]
                new_value = PropsField(
                    annotated_type=inherited_field.annotated_type,
                    default=value,
                    default_factory=None,
                )
                own_fields[key] = new_value

        # Process annotated fields
        for key, annotation in resolved_annotations.items():
            value = namespace.get(key, MISSING)

            if value is MISSING:
                # Field with only annotation, no default value
                value = PropsField(
                    annotated_type=annotation,
                    default=MISSING,
                )
            elif not isinstance(value, PropsField):
                # Field with default value
                value = PropsField(
                    annotated_type=annotation,
                    default=value,
                )
            else:
                # Field is already a PropsField, update annotation
                value = PropsField(
                    annotated_type=annotation,
                    default=value.default,
                    default_factory=value.default_factory,
                )

            own_fields[key] = value

        # Set field names for compatibility
        all_fields = inherited_fields | own_fields
        for field_name, field in all_fields.items():
            field._name = field_name

        # Store field mappings on the class
        namespace["_own_fields"] = own_fields
        namespace["_inherited_fields"] = inherited_fields
        namespace["_fields"] = all_fields

        # Backward compatibility: add __fields__ attribute for Pydantic compatibility
        namespace["__fields__"] = all_fields

        return super().__new__(cls, name, bases, namespace)


class PropsBase(metaclass=PropsBaseMeta):
    """Base for a class containing props that can be serialized as a JS object."""

    def __init__(self, **kwargs):
        """Initialize the props with field values.

        Args:
            **kwargs: The field values to set.
        """
        # Set field values from kwargs with nested object instantiation
        for key, value in kwargs.items():
            field_info = getattr(self.__class__, "_fields", {}).get(key)
            if field_info:
                field_type = field_info.annotated_type

                # Check if this field expects a specific Props type and we got a dict
                if isinstance(value, dict):
                    props_class = _is_props_subclass(field_type)
                    if props_class is not None:
                        value = props_class(**value)

                # Check if this field expects a list of Props and we got a list of dicts
                elif isinstance(value, list):
                    element_type = _get_list_element_type(field_type)
                    if element_type is not None:
                        # Convert each dict in the list to the appropriate Props class
                        value = [
                            element_type(**item) if isinstance(item, dict) else item
                            for item in value
                        ]

            setattr(self, key, value)

        # Set default values for fields not provided
        for field_name, field in getattr(self.__class__, "_fields", {}).items():
            if not hasattr(self, field_name):
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

        # Get all field values
        for field_name in getattr(self.__class__, "_fields", {}):
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


# Register PropsBase serializer to preserve callables (lambdas)
def _register_props_serializer():
    """Register PropsBase serializer that preserves callables."""
    from reflex.utils import serializers

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

    # Register the serializer
    serializers.SERIALIZERS[PropsBase] = serialize_props_base
    serializers.SERIALIZER_TYPES[PropsBase] = dict
    # Clear caches
    serializers.get_serializer.cache_clear()
    serializers.get_serializer_type.cache_clear()


# Register the serializer
_register_props_serializer()


class NoExtrasAllowedProps(metaclass=PropsBaseMeta):
    """A class that holds props to be passed or applied to a component with no extra props allowed."""

    def dict(
        self,
        exclude_none: bool = True,
        include: set[str] | None = None,
        exclude: set[str] | None = None,
        **kwargs,
    ):
        """Convert the object to a dictionary.

        Args:
            exclude_none: Whether to exclude None values.
            include: Fields to include in the output.
            exclude: Fields to exclude from the output.
            **kwargs: Additional keyword arguments (for compatibility).

        Returns:
            The object as a dictionary.
        """
        result = {}

        for field_name in getattr(self.__class__, "_fields", {}):
            if hasattr(self, field_name):
                value = getattr(self, field_name)

                if include is not None and field_name not in include:
                    continue
                if exclude is not None and field_name in exclude:
                    continue

                if exclude_none and value is None:
                    continue

                # Use the same recursive conversion as PropsBase
                value = self._convert_to_camel_case(
                    value, exclude_none, include, exclude
                )

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
        if hasattr(value, "dict") and callable(value.dict):
            # Convert nested PropsBase/NoExtrasAllowedProps objects
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

    @classmethod
    def get_fields(cls) -> dict[str, Any]:
        """Get the fields of the object.

        Returns:
            Dictionary mapping field names to PropsField instances.
        """
        return getattr(cls, "_fields", {})

    def __init__(self, component_name: str | None = None, **kwargs):
        """Initialize the props.

        Args:
            component_name: The custom name of the component.
            kwargs: Kwargs to initialize the props.

        Raises:
            InvalidPropValueError: If invalid props are passed on instantiation.
        """
        component_name = component_name or type(self).__name__

        # Validate fields BEFORE setting them
        known_fields = set(getattr(self.__class__, "_fields", {}).keys())
        provided_fields = set(kwargs.keys())
        invalid_fields = provided_fields - known_fields

        if invalid_fields:
            invalid_fields_str = ", ".join(invalid_fields)
            supported_props_str = ", ".join(f'"{field}"' for field in known_fields)
            msg = f"Invalid prop(s) {invalid_fields_str} for {component_name!r}. Supported props are {supported_props_str}"
            raise InvalidPropValueError(msg)

        # Basic field initialization with nested validation
        for key, value in kwargs.items():
            field_info = getattr(self.__class__, "_fields", {}).get(key)
            if field_info:
                field_type = field_info.annotated_type

                # Check if this field expects a specific Props type and we got a dict
                if isinstance(value, dict):
                    props_class = _is_props_subclass(field_type)
                    if props_class is not None:
                        value = props_class(**value)

                # Check if this field expects a list of Props and we got a list of dicts
                elif isinstance(value, list):
                    element_type = _get_list_element_type(field_type)
                    if element_type is not None:
                        # Convert each dict in the list to the appropriate Props class
                        value = [
                            element_type(**item) if isinstance(item, dict) else item
                            for item in value
                        ]

            setattr(self, key, value)

        for field_name, field in getattr(self.__class__, "_fields", {}).items():
            if not hasattr(self, field_name):
                if field.default is not MISSING:
                    setattr(self, field_name, field.default)
                elif field.default_factory is not None:
                    setattr(self, field_name, field.default_factory())
