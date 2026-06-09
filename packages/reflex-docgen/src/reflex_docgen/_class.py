"""Generate documentation for arbitrary Python classes."""

import collections.abc
import dataclasses
import inspect
import re
from dataclasses import dataclass
from typing import Any, Literal, get_args, get_origin, get_type_hints

from reflex_base.utils.types import is_union
from reflex_base.vars.base import BaseStateMeta
from typing_extensions import TypeAliasType
from typing_inspection.introspection import AnnotationSource, inspect_annotation


@dataclass(frozen=True, slots=True, kw_only=True)
class FieldDocumentation:
    """Hold information about a class field.

    Attributes:
        name: The name of the field.
        type: The resolved type of the field.
        type_display: Concise human-readable type string with module qualifiers stripped and type-alias names preserved.
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


def _literal_value(value: Any) -> str:
    """Return a readable display value for a Literal option.

    Args:
        value: The literal option value.

    Returns:
        The display string for the value.
    """
    return f'"{value}"' if isinstance(value, str) else repr(value)


def _type_name(type_: Any) -> str:
    """Return the short, unqualified name for a leaf type.

    Args:
        type_: The leaf type to name.

    Returns:
        The unqualified type name (e.g. ``Starlette`` for ``starlette.applications.Starlette``).
    """
    name = getattr(type_, "__name__", None)
    if name:
        return name
    return str(type_).rsplit(".", maxsplit=1)[-1]


def format_type(type_: Any) -> str:
    """Return a concise, human-readable string for a type annotation.

    Strips module qualifiers, preserves type-alias names, and renders unions,
    literals, callables, and other generics recursively.

    Args:
        type_: The type annotation to format.

    Returns:
        A concise, human-readable type string.
    """
    if type_ is None or type_ is type(None):
        return "None"
    if isinstance(type_, TypeAliasType):
        return type_.__name__

    origin = get_origin(type_)
    args = get_args(type_)

    if origin is Literal:
        return f"Literal[{', '.join(_literal_value(arg) for arg in args)}]"
    if is_union(type_):
        members = [arg for arg in args if arg is not type(None)]
        rendered = " | ".join(format_type(arg) for arg in members)
        # Surface optionality explicitly: ``X | None`` reads as ``Optional[X]``.
        return f"Optional[{rendered}]" if len(members) != len(args) else rendered
    if origin is collections.abc.Callable:
        *param_part, return_type = args
        params = param_part[0] if param_part else []
        if params is Ellipsis:
            inner = "..."
        elif isinstance(params, list):
            inner = f"[{', '.join(format_type(param) for param in params)}]"
        else:
            inner = format_type(params)
        return f"Callable[{inner}, {format_type(return_type)}]"
    if origin is not None and args:
        return f"{_type_name(origin)}[{', '.join(format_type(arg) for arg in args)}]"
    return _type_name(type_)


_EMPTY_FACTORY_DISPLAY = {
    dict: "{}",
    list: "[]",
    set: "set()",
    tuple: "()",
    frozenset: "frozenset()",
}


def _format_default(value: Any, *, is_factory: bool) -> str | None:
    """Return a stable, readable display for a field default, or None to omit it.

    A raw repr of a function/lambda/factory default carries a volatile memory
    address (e.g. ``<function f at 0x7c67...>``); render a clean name or an
    empty-collection literal instead so the output is readable and deterministic.

    Args:
        value: The default value, or the default_factory when is_factory is True.
        is_factory: Whether value is a dataclass/pydantic default_factory.

    Returns:
        A display string, or None when the default is opaque (e.g. a lambda).
    """
    if is_factory:
        literal = _EMPTY_FACTORY_DISPLAY.get(value)
        if literal is not None:
            return literal
    if isinstance(value, type):
        return value.__name__
    if callable(value):
        name = getattr(value, "__qualname__", "") or getattr(value, "__name__", "")
        return None if not name or "<" in name else name
    return repr(value)


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
        type_display=format_type(unwrapped_type),
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
            default_str = _format_default(f.default, is_factory=False)
        elif f.default_factory is not dataclasses.MISSING:
            default_str = _format_default(f.default_factory, is_factory=True)
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
            default_str = _format_default(field.default, is_factory=False)
        elif field.default_factory is not None:
            default_str = _format_default(field.default_factory, is_factory=True)
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


# Matches a quoted span (group 1) or a dotted module path (group 2 captures the
# final name). Quoted spans are matched first so a dotted value inside a Literal
# (e.g. ``Literal["a.b"]``) is left untouched.
_QUALIFIED_NAME = re.compile(
    r"""("[^"]*"|'[^']*')|\b(?:[A-Za-z_]\w*\.)+([A-Za-z_]\w*)"""
)


def _strip_module_qualifiers(annotation: str) -> str:
    """Collapse dotted module paths in a forward-ref string to bare names.

    Mirrors what format_type does for resolved types: ``contextlib.AbstractContextManager``
    becomes ``AbstractContextManager``. Names inside quoted Literal values are
    preserved.

    Args:
        annotation: The annotation string.

    Returns:
        The annotation with module qualifiers removed.
    """
    return _QUALIFIED_NAME.sub(
        lambda match: match.group(1) if match.group(1) is not None else match.group(2),
        annotation,
    )


def _split_top_level_union(annotation: str) -> list[str]:
    """Split a forward-ref annotation into its top-level ``|`` union members.

    Splits only at ``|`` outside any brackets, so a union nested inside a
    subscript (e.g. the ``int | None`` in ``dict[str, int | None]``) stays intact.

    Args:
        annotation: The annotation string.

    Returns:
        The top-level union members, each stripped of surrounding whitespace.
    """
    members: list[str] = []
    depth = 0
    start = 0
    for i, char in enumerate(annotation):
        if char in "[(":
            depth += 1
        elif char in ")]":
            depth -= 1
        elif char == "|" and depth == 0:
            members.append(annotation[start:i].strip())
            start = i + 1
    members.append(annotation[start:].strip())
    return members


def _optional_from_string(annotation: str) -> str:
    """Rewrite a forward-ref union containing ``None`` as Optional[...].

    Method-parameter annotations referencing a TYPE_CHECKING-only name cannot be
    resolved to real types, so they are rendered from the forward-ref string
    directly. When the top-level union includes ``None`` in any position, the
    remaining members are wrapped in Optional[...] so optionality reads the same
    way format_type renders it. ``None`` nested inside a subscript is left alone.

    Args:
        annotation: The annotation string.

    Returns:
        The annotation, with top-level ``None`` rewritten as Optional[...].
    """
    members = _split_top_level_union(annotation)
    if len(members) > 1 and "None" in members:
        inner = " | ".join(member for member in members if member != "None")
        return f"Optional[{inner}]"
    return annotation


def _format_annotation(annotation: Any) -> str:
    """Render a parameter or return annotation as a concise type string.

    Real type objects go through format_type. Forward-ref strings (from
    ``from __future__ import annotations``) keep the author's readable names
    rather than expanding aliases, with module qualifiers stripped and
    optionality normalized to match format_type's output.

    Args:
        annotation: The annotation, either a real type or a forward-ref string.

    Returns:
        The rendered annotation string.
    """
    if isinstance(annotation, str):
        return _optional_from_string(_strip_module_qualifiers(annotation))
    return format_type(annotation)


def _format_signature(fn: Any) -> str:
    """Return a readable call signature for a function or method.

    Drops self/cls, renders each annotation independently (real types through
    format_type, forward-ref strings kept verbatim with optionality normalized),
    and cleans default values. Annotations are taken as written rather than
    bulk-resolved, so one TYPE_CHECKING-only name does not affect the others.

    Args:
        fn: The function or method to render.

    Returns:
        A signature string such as ``(route: Optional[str] = None) -> None``.
    """
    try:
        sig = inspect.signature(fn)
    except (ValueError, TypeError):
        return "(...)"

    empty = inspect.Parameter.empty
    parts: list[str] = []
    keyword_separated = False
    for name, param in sig.parameters.items():
        if name in ("self", "cls"):
            continue

        if param.kind is inspect.Parameter.VAR_POSITIONAL:
            prefix, keyword_separated = "*", True
        elif param.kind is inspect.Parameter.VAR_KEYWORD:
            prefix = "**"
        elif param.kind is inspect.Parameter.KEYWORD_ONLY and not keyword_separated:
            parts.append("*")
            keyword_separated, prefix = True, ""
        else:
            prefix = ""

        text = prefix + name

        if param.annotation is not empty:
            text += f": {_format_annotation(param.annotation)}"

        if param.default is not empty:
            default = _format_default(param.default, is_factory=False)
            text += f" = {default if default is not None else '...'}"

        parts.append(text)

    rendered = f"({', '.join(parts)})"

    if sig.return_annotation is not inspect.Signature.empty:
        rendered += f" -> {_format_annotation(sig.return_annotation)}"

    return rendered


def _get_methods(cls: type) -> tuple[MethodDocumentation, ...]:
    """Extract public documented methods from a class.

    Args:
        cls: The class to extract methods from.

    Returns:
        A tuple of MethodDocumentation objects.
    """
    # Dataclass/state fields whose default is a function live in __dict__ as that
    # function; they are fields, not methods, so exclude them.
    if dataclasses.is_dataclass(cls):
        field_names = {f.name for f in dataclasses.fields(cls)}
    elif isinstance(cls, BaseStateMeta):
        field_names = set(cls.__fields__)
    else:
        field_names = set()

    result = []
    for name, obj in cls.__dict__.items():
        if name.startswith("_") or name == "Config" or name in field_names:
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

        result.append(
            MethodDocumentation(
                name=name,
                signature=_format_signature(fn),
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
