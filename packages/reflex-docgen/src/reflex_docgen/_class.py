"""Generate documentation for arbitrary Python classes."""

import dataclasses
import inspect
from dataclasses import dataclass
from typing import Annotated, Any, get_args, get_type_hints

from typing_extensions import Doc
from typing_inspection.introspection import AnnotationSource, inspect_annotation


@dataclass(frozen=True, slots=True, kw_only=True)
class FieldDocumentation:
    """Hold information about a class field."""

    name: Annotated[str, Doc("The name of the field.")]

    type: Annotated[
        Any, Doc("The resolved type of the field, unwrapped from Annotated.")
    ]

    type_display: Annotated[
        str,
        Doc(
            "Human-readable type string (no Annotated, no Var wrapper). "
            "Uses __name__ for simple types, str() for generics."
        ),
    ]

    description: Annotated[
        str | None, Doc("The description extracted from Doc() metadata or field.doc.")
    ]

    default: Annotated[
        str | None, Doc("The repr() of the default value, or None if no default.")
    ]


@dataclass(frozen=True, slots=True, kw_only=True)
class MethodDocumentation:
    """Hold information about a class method."""

    name: Annotated[str, Doc("The name of the method.")]

    signature: Annotated[str, Doc("The string representation of the method signature.")]

    description: Annotated[
        str | None,
        Doc("The docstring, truncated before 'Args:' or 'Returns:' sections."),
    ]


@dataclass(frozen=True, slots=True, kw_only=True)
class ClassDocumentation:
    """Documentation for an arbitrary Python class."""

    name: Annotated[
        str,
        Doc("The fully qualified name (module.qualname) of the class."),
    ]

    description: Annotated[str | None, Doc("The cleaned docstring of the class.")]

    fields: Annotated[
        tuple[FieldDocumentation, ...],
        Doc("Instance fields (from dataclass fields or __fields__)."),
    ] = ()

    class_fields: Annotated[
        tuple[FieldDocumentation, ...],
        Doc("Class variables (from __class_vars__ on rx.Base subclasses)."),
    ] = ()

    methods: Annotated[
        tuple[MethodDocumentation, ...],
        Doc("Public methods that have docstrings."),
    ] = ()


def _type_display(type_: Any) -> str:
    """Return a human-readable type string.

    Args:
        type_: The type to display.

    Returns:
        A human-readable type string.
    """
    if get_args(type_):
        return str(type_)
    return getattr(type_, "__name__", str(type_))


def _extract_field_doc(hint: Any, field_doc: str | None) -> tuple[Any, str | None]:
    """Extract the unwrapped type and description from a type hint.

    Args:
        hint: The type hint (possibly Annotated).
        field_doc: The field.doc attribute value (takes priority).

    Returns:
        A tuple of (unwrapped_type, description).
    """
    inspected = inspect_annotation(hint, annotation_source=AnnotationSource.ANY)
    unwrapped_type = inspected.type
    description = field_doc
    if description is None:
        for meta in inspected.metadata:
            if isinstance(meta, Doc):
                description = meta.documentation
                break
    return unwrapped_type, description


def _build_field_documentation(
    name: str, hint: Any, field_doc: str | None, default_value: str | None
) -> FieldDocumentation | None:
    """Build a FieldDocumentation from field info, or None if private.

    Args:
        name: The field name.
        hint: The type hint.
        field_doc: The field.doc attribute value.
        default_value: The repr'd default value, or None.

    Returns:
        A FieldDocumentation, or None if the field should be skipped.
    """
    if name.startswith("_"):
        return None

    unwrapped_type, description = _extract_field_doc(hint, field_doc)

    if description is not None and "PRIVATE" in description:
        return None

    return FieldDocumentation(
        name=name,
        type=unwrapped_type,
        type_display=_type_display(unwrapped_type),
        description=description,
        default=default_value,
    )


def _get_dataclass_fields(cls: type) -> tuple[FieldDocumentation, ...]:
    """Extract fields from a dataclass.

    Args:
        cls: The dataclass to extract fields from.

    Returns:
        A tuple of FieldDocumentation objects.
    """
    hints = get_type_hints(cls, include_extras=True)
    result = []
    for f in dataclasses.fields(cls):
        hint = hints.get(f.name, f.type)
        field_doc = getattr(f, "doc", None)

        if f.default is not dataclasses.MISSING:
            default_str = repr(f.default)
        elif f.default_factory is not dataclasses.MISSING:
            default_str = repr(f.default_factory)
        else:
            default_str = None

        doc = _build_field_documentation(f.name, hint, field_doc, default_str)
        if doc is not None:
            result.append(doc)

    return tuple(result)


def _get_base_fields(cls: type) -> tuple[FieldDocumentation, ...]:
    """Extract instance fields from a class with __fields__ (e.g. rx.Base subclass).

    Args:
        cls: The class to extract fields from.

    Returns:
        A tuple of FieldDocumentation objects.
    """
    hints = get_type_hints(cls, include_extras=True)
    fields_dict = cls.__fields__  # type: ignore[attr-defined]
    result = []
    for name, field in fields_dict.items():
        hint = hints.get(name, getattr(field, "outer_type_", type(None)))
        field_doc = getattr(field, "doc", None)

        default = getattr(field, "default", dataclasses.MISSING)
        if default is not dataclasses.MISSING:
            default_str = repr(default)
        else:
            factory = getattr(field, "default_factory", None)
            default_str = repr(factory) if factory is not None else None

        doc = _build_field_documentation(name, hint, field_doc, default_str)
        if doc is not None:
            result.append(doc)

    return tuple(result)


def _get_class_vars(cls: type) -> tuple[FieldDocumentation, ...]:
    """Extract class variables from __class_vars__.

    Args:
        cls: The class to extract class variables from.

    Returns:
        A tuple of FieldDocumentation objects.
    """
    class_vars = getattr(cls, "__class_vars__", None)
    if not class_vars:
        return ()

    hints = get_type_hints(cls, include_extras=True)
    result = []
    for name in class_vars:
        hint = hints.get(name, type(None))
        doc = _build_field_documentation(name, hint, None, None)
        if doc is not None:
            result.append(doc)

    return tuple(result)


def _get_methods(cls: type) -> tuple[MethodDocumentation, ...]:
    """Extract public documented methods from a class.

    Args:
        cls: The class to extract methods from.

    Returns:
        A tuple of MethodDocumentation objects.
    """
    result = []
    for name, obj in cls.__dict__.items():
        if name.startswith("_") or name == "Config":
            continue

        fn = obj
        if isinstance(obj, (classmethod, staticmethod)):
            fn = obj.__func__

        if not callable(fn):
            continue

        docstring = getattr(fn, "__doc__", None)
        if not docstring:
            continue

        # Truncate docstring before Args: or Returns:
        for marker in ("Args:", "Returns:"):
            idx = docstring.find(marker)
            if idx != -1:
                docstring = docstring[:idx]
                break
        docstring = docstring.strip() or None

        try:
            sig = str(inspect.signature(fn))
        except (ValueError, TypeError):
            sig = "(...)"

        result.append(
            MethodDocumentation(
                name=name,
                signature=sig,
                description=docstring,
            )
        )

    return tuple(result)


def generate_class_documentation(cls: type) -> ClassDocumentation:
    """Generate documentation for an arbitrary Python class.

    Supports dataclasses, rx.Base subclasses (classes with __fields__),
    and other classes (methods only).

    Args:
        cls: The class to generate documentation for.

    Returns:
        The generated documentation for the class.
    """
    description = inspect.cleandoc(cls.__doc__) if cls.__doc__ else None

    if dataclasses.is_dataclass(cls):
        fields = _get_dataclass_fields(cls)
    elif hasattr(cls, "__fields__"):
        fields = _get_base_fields(cls)
    else:
        fields = ()

    class_fields = _get_class_vars(cls)
    methods = _get_methods(cls)

    return ClassDocumentation(
        name=f"{cls.__module__}.{cls.__qualname__}",
        description=description,
        fields=fields,
        class_fields=class_fields,
        methods=methods,
    )
