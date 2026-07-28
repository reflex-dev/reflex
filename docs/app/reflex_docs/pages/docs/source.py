import itertools
from collections.abc import Callable, Sequence

import reflex as rx
from reflex_docgen import (
    FieldDocumentation,
    MethodDocumentation,
    generate_class_documentation,
)

from reflex_docs.docgen_pipeline import render_markdown
from reflex_docs.templates.docpage import h1_comp, h2_comp

table_header_class_name = (
    "font-small text-secondary-12 text-normal w-auto justify-start pl-4 font-bold"
)

description_cell_class_name = "font-small text-secondary-11"


def format_field(field: FieldDocumentation) -> rx.Component:
    type_str = field.type_display
    if field.default is not None:
        type_str += f" = {field.default}"
    return rx.code(field.name, ": ", type_str, class_name="code-style")


def stacked_description_rows(
    leading_cells: Sequence[tuple[rx.Component, str]],
    description: Callable[[], rx.Component],
    breakpoint: str,
    description_cell_class: str = "",
) -> tuple[rx.Component, rx.Component]:
    """Build a table row whose description column stacks on narrow containers.

    On containers at least as wide as the Tailwind ``breakpoint``, the
    description renders as the last cell of a single row. Below that, it
    drops to a second full-width row so the table never needs horizontal
    scrolling just to read descriptions. The nearest ancestor with the
    ``@container`` class defines the measured width.

    Args:
        leading_cells: The non-description cells as (content, extra cell classes).
        description: Description factory, called once per rendered copy.
        breakpoint: Tailwind container breakpoint (e.g. ``"4xl"``) above which
            the description stays in-row.
        description_cell_class: Extra classes for the in-row description cell.

    Returns:
        The main row and the narrow-only description row.
    """
    return (
        rx.table.row(
            *[
                rx.table.cell(
                    content,
                    # When stacked, the description row below carries the divider.
                    class_name=f"{extra_class} @max-{breakpoint}:shadow-none".strip(),
                )
                for content, extra_class in leading_cells
            ]
            + [
                rx.table.cell(
                    description(),
                    class_name=f"{description_cell_class_name} {description_cell_class} hidden @{breakpoint}:table-cell",
                ),
            ]
        ),
        rx.table.row(
            rx.table.cell(
                description(),
                col_span=len(leading_cells),
                class_name=description_cell_class_name,
            ),
            class_name=f"@{breakpoint}:hidden",
        ),
    )


def stacked_description_header(
    headers: list[str],
    breakpoint: str,
    header_class: str = table_header_class_name,
) -> rx.Component:
    """Build a table header whose last (description) column hides when stacked.

    Args:
        headers: All column headers; the last one is the description column.
        breakpoint: Tailwind container breakpoint matching the body rows.
        header_class: Base classes for every header cell.

    Returns:
        The table header component.
    """
    return rx.table.header(
        rx.table.row(
            *[
                rx.table.column_header_cell(header, class_name=header_class)
                for header in headers[:-1]
            ]
            + [
                rx.table.column_header_cell(
                    headers[-1],
                    class_name=f"{header_class} hidden @{breakpoint}:table-cell",
                ),
            ]
        )
    )


def format_fields(
    headers: list[str],
    fields: tuple[FieldDocumentation, ...],
    env_var_prefix: str | None = None,
) -> rx.Component:
    # A table with the extra env var column needs more room to fit the
    # description in-row, so it stacks at a wider container breakpoint.
    breakpoint = "4xl" if env_var_prefix is not None else "2xl"
    if env_var_prefix is not None:
        headers = [headers[0], "Environment Variable", *headers[1:]]

    def field_rows(field: FieldDocumentation) -> tuple[rx.Component, rx.Component]:
        leading_cells = [(format_field(field), "")]
        if env_var_prefix is not None:
            leading_cells.append((
                rx.code(
                    f"{env_var_prefix}{field.name.upper()}",
                    class_name="code-style",
                ),
                "",
            ))
        return stacked_description_rows(
            leading_cells,
            lambda: render_markdown(field.description or ""),
            breakpoint,
        )

    return rx.table.root(
        stacked_description_header(headers, breakpoint),
        rx.table.body(
            *itertools.chain.from_iterable(field_rows(field) for field in fields),
        ),
    )


def format_methods(methods: tuple[MethodDocumentation, ...]) -> rx.Component:
    return rx.table.root(
        rx.table.header(
            rx.table.row(
                rx.table.column_header_cell("Signature"),
                rx.table.column_header_cell("Description"),
            )
        ),
        rx.table.body(
            *[
                rx.table.row(
                    rx.table.cell(
                        rx.code(
                            method.name + method.signature,
                            class_name="code-style",
                        ),
                        white_space="normal",
                    ),
                    rx.table.cell(
                        method.description or "",
                        white_space="normal",
                        class_name="font-small text-secondary-11 text-nowrap",
                    ),
                )
                for method in methods
            ],
        ),
    )


def generate_docs(
    title: str,
    cls: type,
    env_var_prefix: str | None = None,
) -> rx.Component:
    doc = generate_class_documentation(cls)

    return rx.box(
        h1_comp(text=title.title()),
        rx.code(doc.name, class_name="code-style text-[18px]"),
        rx.divider(),
        render_markdown(doc.description or ""),
        (
            rx.box(
                h2_comp(text="Class Fields"),
                format_fields(["Prop", "Description"], doc.class_fields),
                overflow="auto",
                class_name="@container",
            )
            if doc.class_fields
            else rx.fragment()
        ),
        (
            rx.box(
                h2_comp(text="Fields"),
                format_fields(["Prop", "Description"], doc.fields, env_var_prefix),
                overflow="auto",
                class_name="@container",
            )
            if doc.fields
            else rx.fragment()
        ),
        rx.box(
            h2_comp(text="Methods"),
            format_methods(doc.methods),
        ),
    )
