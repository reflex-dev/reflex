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


def format_field(field: FieldDocumentation) -> rx.Component:
    type_str = field.type_display
    if field.default is not None:
        type_str += f" = {field.default}"
    return rx.code(field.name, ": ", type_str, class_name="code-style")


def format_fields(
    headers: list[str],
    fields: tuple[FieldDocumentation, ...],
    env_var_prefix: str | None = None,
) -> rx.Component:
    if env_var_prefix is not None:
        headers = [headers[0], "Environment Variable", *headers[1:]]
    return (
        rx.table.root(
            rx.table.header(
                rx.table.row(*[
                    rx.table.column_header_cell(
                        header, class_name=table_header_class_name
                    )
                    for header in headers
                ])
            ),
            rx.table.body(
                *[
                    rx.table.row(
                        rx.table.cell(
                            format_field(field),
                        ),
                        *(
                            [
                                rx.table.cell(
                                    rx.code(
                                        f"{env_var_prefix}{field.name.upper()}",
                                        class_name="code-style",
                                    ),
                                )
                            ]
                            if env_var_prefix is not None
                            else []
                        ),
                        rx.table.cell(
                            render_markdown(field.description or ""),
                            class_name="font-small text-secondary-11",
                        ),
                    )
                    for field in fields
                ],
            ),
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
            )
            if doc.class_fields
            else rx.fragment()
        ),
        (
            rx.box(
                h2_comp(text="Fields"),
                format_fields(["Prop", "Description"], doc.fields, env_var_prefix),
                overflow="auto",
            )
            if doc.fields
            else rx.fragment()
        ),
        rx.box(
            h2_comp(text="Methods"),
            format_methods(doc.methods),
        ),
    )
