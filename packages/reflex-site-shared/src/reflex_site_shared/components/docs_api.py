"""Reusable API-reference tables for Reflex documentation sites."""

from __future__ import annotations

import inspect
import re
from collections.abc import Callable, Collection, Mapping, Sequence
from typing import Any

import reflex as rx

DOCS_API_CELL_CLASS = "min-w-0 px-4 py-3 align-top"
DOCS_API_HEADER_CLASS = "px-4 py-3 text-left text-xs font-semibold text-secondary-11"
_DOCS_API_COLUMN_WIDTHS = ("w-[20%]", "w-[25%]", "w-[55%]")
_NON_ID_CHARACTER = re.compile(r"[^a-z0-9]+")


def docs_api_table(
    *rows: rx.Component,
    headers: Sequence[str] = ("Prop", "Type", "Description"),
    widths: Sequence[str] = _DOCS_API_COLUMN_WIDTHS,
) -> rx.Component:
    """Render the shared API-reference table shell.

    Args:
        *rows: Pre-rendered table rows.
        headers: Column labels.
        widths: Tailwind width classes corresponding to the headers.

    Returns:
        Styled documentation table shared by component reference pages.

    Raises:
        ValueError: If headers and widths do not have matching lengths.
    """
    if len(headers) != len(widths):
        msg = "API table headers and widths must have matching lengths"
        raise ValueError(msg)
    return rx.box(
        rx.el.table(
            rx.el.thead(
                rx.el.tr(
                    *(
                        rx.el.th(
                            header,
                            class_name=f"{DOCS_API_HEADER_CLASS} {width}",
                        )
                        for header, width in zip(headers, widths, strict=True)
                    )
                ),
                class_name="border-b border-secondary-4 bg-secondary-2",
            ),
            rx.el.tbody(*rows, class_name="bg-secondary-1"),
            class_name="w-full table-fixed border-collapse text-left",
        ),
        class_name=(
            "mb-4 w-full min-w-0 overflow-hidden rounded-xl border "
            "border-secondary-4 bg-secondary-1 shadow-small"
        ),
    )


def docs_api_row(
    *cells: rx.Component,
    class_name: str = "",
    **props: Any,
) -> rx.Component:
    """Render one API-reference table row.

    Args:
        *cells: Row cells.
        class_name: Additional row classes.
        **props: Additional Reflex table-row props.

    Returns:
        Styled table row.
    """
    base_class = (
        "border-b border-secondary-4 last:border-b-0 transition-colors "
        "hover:bg-secondary-2"
    )
    return rx.el.tr(
        *cells,
        class_name=f"{base_class} {class_name}".strip(),
        **props,
    )


def docs_api_cell(child: rx.Component, width: str) -> rx.Component:
    """Render one API-reference table cell.

    Args:
        child: Cell content.
        width: Tailwind width class.

    Returns:
        Styled table cell.
    """
    return rx.el.td(child, class_name=f"{DOCS_API_CELL_CLASS} {width}")


def _format_annotation(annotation: Any) -> str:
    """Format an inspected annotation for documentation.

    Args:
        annotation: Inspected parameter annotation.

    Returns:
        Human-readable annotation text.
    """
    if annotation is inspect.Parameter.empty:
        return "Any"
    if isinstance(annotation, str):
        return annotation.replace("typing.", "")
    return getattr(annotation, "__name__", str(annotation).replace("typing.", ""))


def _format_default(default: Any) -> str | None:
    """Format a stable, compact default value.

    Args:
        default: Inspected parameter default.

    Returns:
        Stable default text, or ``None`` for an opaque default.
    """
    if callable(default):
        return getattr(default, "__name__", type(default).__name__)
    value = repr(default)
    if " object at 0x" in value:
        return None
    return value if len(value) <= 80 else f"{value[:77]}..."


def _parameter_descriptions(docstring: str) -> dict[str, str]:
    """Extract a Google-style Args section from a docstring.

    Args:
        docstring: Callable docstring to inspect.

    Returns:
        Parameter names mapped to their descriptions.
    """
    descriptions: dict[str, str] = {}
    current: str | None = None
    in_args = False
    for line in docstring.splitlines():
        stripped = line.strip()
        if stripped in {"Args:", "Arguments:", "Parameters:"}:
            in_args = True
            current = None
            continue
        if not in_args:
            continue
        if stripped and not line.startswith((" ", "\t")):
            break
        if not stripped:
            continue
        if ":" in stripped and not stripped.startswith(":"):
            name, description = stripped.split(":", 1)
            name = name.split("(", 1)[0].strip().lstrip("*")
            if name.isidentifier():
                current = name
                descriptions[current] = description.strip()
                continue
        if current is not None:
            descriptions[current] = f"{descriptions[current]} {stripped}".strip()
    return descriptions


def _summary(docstring: str) -> str:
    """Return the opening paragraph of a docstring.

    Args:
        docstring: Callable docstring to summarize.

    Returns:
        Single-line summary text.
    """
    return docstring.strip().split("\n\n", 1)[0].replace("\n", " ")


def _heading_id(name: str) -> str:
    """Convert a display name to a safe HTML fragment identifier.

    Args:
        name: Public API display name.

    Returns:
        Lowercase kebab-case fragment identifier.
    """
    return _NON_ID_CHARACTER.sub("-", name.lower()).strip("-")


def callable_api_reference(
    function: Callable[..., Any],
    *,
    display_name: str | None = None,
    parameter_descriptions: Mapping[str, str] | None = None,
    exclude_parameters: Collection[str] = (),
) -> rx.Component:
    """Generate a Reflex-style props table for a Python callable.

    Args:
        function: Callable whose public signature should be documented.
        display_name: Optional public name shown above the table.
        parameter_descriptions: Optional descriptions overriding docstring text.
        exclude_parameters: Implementation-only parameters to omit.

    Returns:
        Callable description followed by a generated props table.
    """
    signature = inspect.signature(function)
    docstring = inspect.getdoc(function) or ""
    descriptions = _parameter_descriptions(docstring)
    descriptions.update(parameter_descriptions or {})
    rows: list[rx.Component] = []
    for parameter in signature.parameters.values():
        if parameter.name in exclude_parameters:
            continue
        prefix = (
            "**"
            if parameter.kind is inspect.Parameter.VAR_KEYWORD
            else "*"
            if parameter.kind is inspect.Parameter.VAR_POSITIONAL
            else ""
        )
        is_required = parameter.default is inspect.Parameter.empty
        default = None if is_required else _format_default(parameter.default)
        description = descriptions.get(parameter.name, "")
        if not description:
            if parameter.kind is inspect.Parameter.VAR_POSITIONAL:
                description = "Additional positional arguments."
            elif parameter.kind is inspect.Parameter.VAR_KEYWORD:
                description = "Additional keyword arguments."
            elif is_required:
                description = "Required."
            elif default is None:
                description = "Optional."
            else:
                description = f"Defaults to {default}."
        rows.append(
            docs_api_row(
                docs_api_cell(
                    rx.code(
                        f"{prefix}{parameter.name}",
                        class_name="code-style text-nowrap leading-normal",
                    ),
                    _DOCS_API_COLUMN_WIDTHS[0],
                ),
                docs_api_cell(
                    rx.code(
                        _format_annotation(parameter.annotation),
                        color_scheme="gray",
                        variant="soft",
                        class_name=(
                            "code-style leading-normal whitespace-normal break-words"
                        ),
                    ),
                    _DOCS_API_COLUMN_WIDTHS[1],
                ),
                docs_api_cell(
                    rx.text(
                        description,
                        class_name=(
                            "font-small text-secondary-11 whitespace-normal "
                            "leading-snug break-words"
                        ),
                    ),
                    _DOCS_API_COLUMN_WIDTHS[2],
                ),
            )
        )
    name = display_name or function.__name__
    return rx.box(
        rx.heading(
            name,
            as_="h3",
            id=_heading_id(name),
            class_name="font-large text-secondary-12 mt-8 mb-2",
        ),
        rx.text(
            _summary(docstring),
            class_name="font-[475] text-secondary-11 mb-4 leading-7",
        )
        if docstring
        else rx.fragment(),
        rx.heading(
            "Props",
            as_="h4",
            class_name="font-base text-secondary-12 mt-4 mb-2",
        ),
        docs_api_table(*rows),
        class_name="w-full",
    )


def callable_api_group(
    *functions: Callable[..., Any],
    namespace: str = "",
) -> rx.Component:
    """Render generated API tables for a group of callables.

    Args:
        *functions: Public functions to document in display order.
        namespace: Optional display prefix such as ``fc``.

    Returns:
        A group of generated callable reference sections.
    """
    prefix = f"{namespace}." if namespace else ""
    return rx.box(
        *(
            callable_api_reference(
                function,
                display_name=f"{prefix}{function.__name__}",
            )
            for function in functions
        ),
        class_name="flex w-full flex-col",
    )


__all__ = [
    "DOCS_API_CELL_CLASS",
    "DOCS_API_HEADER_CLASS",
    "callable_api_group",
    "callable_api_reference",
    "docs_api_cell",
    "docs_api_row",
    "docs_api_table",
]
