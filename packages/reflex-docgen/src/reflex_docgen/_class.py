"""Generate documentation for arbitrary Python classes."""

import dataclasses
import inspect
from dataclasses import dataclass
from typing import Any, get_args, get_type_hints

from reflex_base.vars.base import BaseStateMeta
from typing_inspection.introspection import AnnotationSource, inspect_annotation


@dataclass(frozen=True, slots=True, kw_only=True)
class FieldDocumentation:
    """Hold information about a class field.

    Attributes:
        name: The name of the field.
        type: The resolved type of the field.
        type_display: Human-readable type string (no Var wrapper). Uses __name__ for simple types, str() for generics.
        description: The description extracted from the class docstring or field.doc.
        default: The repr() of the default value, or None if no default.
    """

    name: str

    type: Any

    type_display: str

    description: str | None

    default: str | None


@dataclass(frozen=True, slots=True, kw_only=True)
class MethodDocumentation:
    """Hold information about a class method.

    Attributes:
        name: The name of the method.
        signature: The string representation of the method signature.
        description: The docstring, truncated before 'Args:' or 'Returns:' sections.
    """

    name: str

    signature: str

    description: str | None


@dataclass(frozen=True, slots=True, kw_only=True)
class ClassDocumentation:
    """Documentation for an arbitrary Python class.

    Attributes:
        name: The fully qualified name (module.qualname) of the class.
        description: The cleaned docstring of the class.
        fields: Instance fields (from dataclass fields or rx.State __fields__).
        class_fields: Class variables (from __class_vars__ on rx.Base subclasses).
        methods: Public methods that have docstrings.
    """

    name: str

    description: str | None

    fields: tuple[FieldDocumentation, ...] = ()

    class_fields: tuple[FieldDocumentation, ...] = ()

    methods: tuple[MethodDocumentation, ...] = ()


def _parse_docstring_attributes(cls: type) -> dict[str, str]:
    """Parse an Attributes section from a class docstring using griffe.

    Args:
        cls: The class whose docstring to parse.

    Returns:
        A mapping from attribute name to description string.
    """
    from griffe import Docstring, Parser  # provided by griffelib

    doc = cls.__doc__
    if not doc:
        return {}

    parsed = Docstring(inspect.cleandoc(doc)).parse(Parser.auto)
    return {
        attr.name: attr.description
        for section in parsed
        if section.kind.value == "attributes"
        for attr in section.value
    }


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
        hint: The type hint.
        field_doc: The field.doc attribute value.

    Returns:
        A tuple of (unwrapped_type, description).
    """
    inspected = inspect_annotation(hint, annotation_source=AnnotationSource.ANY)
    return inspected.type, field_doc


def _build_field_documentation(
    name: str,
    hint: Any,
    field_doc: str | None,
    default_value: str | None,
    docstring_desc: str | None = None,
) -> FieldDocumentation | None:
    """Build a FieldDocumentation from field info, or None if private.

    Args:
        name: The field name.
        hint: The type hint.
        field_doc: The field.doc attribute value.
        default_value: The repr'd default value, or None.
        docstring_desc: Description from the class docstring Attributes section (fallback).

    Returns:
        A FieldDocumentation, or None if the field should be skipped.
    """
    if name.startswith("_"):
        return None

    unwrapped_type, description = _extract_field_doc(hint, field_doc)

    # Fall back to docstring Attributes section if no description found.
    if description is None and docstring_desc is not None:
        description = docstring_desc

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
    docstring_attrs = _parse_docstring_attributes(cls)
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

        doc = _build_field_documentation(
            f.name, hint, field_doc, default_str, docstring_attrs.get(f.name)
        )
        if doc is not None:
            result.append(doc)

    return tuple(result)


def _get_state_fields(cls: BaseStateMeta) -> tuple[FieldDocumentation, ...]:
    """Extract instance fields from an rx.State subclass via __fields__.

    Args:
        cls: The class to extract fields from.

    Returns:
        A tuple of FieldDocumentation objects.
    """
    hints = get_type_hints(cls, include_extras=True)
    docstring_attrs = _parse_docstring_attributes(cls)
    fields_dict = cls.__fields__
    result = []
    for name, field in fields_dict.items():
        hint = hints.get(name, field.outer_type_)

        if field.default is not dataclasses.MISSING:
            default_str = repr(field.default)
        elif field.default_factory is not None:
            default_str = repr(field.default_factory)
        else:
            default_str = None

        doc = _build_field_documentation(
            name, hint, None, default_str, docstring_attrs.get(name)
        )
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
    docstring_attrs = _parse_docstring_attributes(cls)
    result = []
    for name in class_vars:
        hint = hints.get(name, type(None))
        doc = _build_field_documentation(
            name, hint, None, None, docstring_attrs.get(name)
        )
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

    Supports dataclasses, rx.State subclasses, and other classes (methods only).

    Args:
        cls: The class to generate documentation for.

    Returns:
        The generated documentation for the class.
    """
    try:
        description = inspect.cleandoc(cls.__doc__) if cls.__doc__ else None

        if dataclasses.is_dataclass(cls):
            fields = _get_dataclass_fields(cls)
        elif isinstance(cls, BaseStateMeta):
            fields = _get_state_fields(cls)
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
    except Exception as e:
        import sys

        if sys.version_info >= (3, 11):
            e.add_note(
                f"Error generating documentation for class {cls.__module__}.{cls.__qualname__}"
            )
        raise
