"""Shared layout for generated API reference pages."""

import inspect
import io
import tokenize

import reflex as rx
from griffe import Docstring, Parser
from reflex_docgen import (
    FieldDocumentation,
    MethodDocumentation,
    generate_class_documentation,
)

from reflex_docs.docgen_pipeline import render_markdown
from reflex_docs.templates.docpage import h1_comp, h2_comp


def multiline_signature(method: MethodDocumentation) -> str:
    """Wrap long signatures at parameter boundaries without splitting nested types."""
    signature = method.name + method.signature
    if len(signature) <= 88:
        return signature
    depth = 0
    start = signature.index("(") + 1
    parts = []
    for token in tokenize.generate_tokens(io.StringIO(signature).readline):
        if token.type != tokenize.OP:
            continue
        if token.string in "([{":
            depth += 1
        elif token.string in ")]}":
            depth -= 1
            if depth == 0:
                last = signature[start : token.start[1]].strip()
                if not last and not parts:
                    return signature
                parts.append(last)
                return (
                    signature[: signature.index("(") + 1]
                    + "\n    "
                    + ",\n    ".join(parts)
                    + ",\n"
                    + signature[token.start[1] :]
                )
        elif token.string == "," and depth == 1:
            parts.append(signature[start : token.start[1]].strip())
            start = token.end[1]
    return signature


def member_heading(name: str, *, compact: bool = False) -> rx.Component:
    """Create a compact, directly linkable API member heading."""
    return rx.el.h3(
        rx.el.a(
            name,
            href=f"#{name.lower()}",
            class_name="text-foreground hover:!text-foreground hover:underline underline-offset-4",
        ),
        id=name.lower(),
        class_name=(
            "m-0 font-mono font-medium leading-6 scroll-mt-32 [overflow-wrap:anywhere] "
            + ("text-sm" if compact else "text-lg")
        ),
    )


def reference_description(text: str) -> rx.Component:
    """Use compact, consistent prose spacing within reference entries."""
    return rx.el.div(
        render_markdown(text),
        class_name="min-w-0 text-foreground [&_p]:!my-0 [&_p]:!text-sm [&_p]:!leading-6 [&_p+p]:!mt-3",
    )


def reference_row(identity: rx.Component, description: str) -> rx.Component:
    """Align field, parameter, and exception details in the same responsive grid."""
    return rx.el.div(
        identity,
        reference_description(description),
        class_name="grid grid-cols-1 gap-2 border-b border-border py-3 md:grid-cols-[minmax(0,0.85fr)_minmax(0,1.15fr)] md:gap-8 [&>div]:min-w-0",
    )


def field_row(
    field: FieldDocumentation, env_var_prefix: str | None = None
) -> rx.Component:
    """Separate a field's identity and metadata from its prose description."""
    metadata = [
        rx.el.code(
            field.type_display,
            class_name="min-w-0 font-mono text-xs leading-5 text-muted-foreground [overflow-wrap:anywhere]",
        )
    ]
    if field.default is not None:
        metadata.append(
            rx.el.p(
                "Default: ",
                rx.el.code(
                    field.default, class_name="font-mono [overflow-wrap:anywhere]"
                ),
                class_name="m-0 text-xs leading-5 text-muted-foreground",
            )
        )
    if env_var_prefix is not None:
        metadata.append(
            rx.el.code(
                f"{env_var_prefix}{field.name.upper()}",
                class_name="min-w-0 font-mono text-xs leading-5 text-muted-foreground [overflow-wrap:anywhere]",
            )
        )
    return reference_row(
        rx.el.div(
            member_heading(field.name, compact=True),
            rx.el.div(
                *metadata,
                class_name="flex min-w-0 flex-wrap items-baseline gap-x-3 gap-y-1",
            ),
            class_name="flex min-w-0 flex-col gap-1",
        ),
        field.description or "",
    )


def method_details(cls: type, method: MethodDocumentation) -> list[rx.Component]:
    """Render parameter, return, yield, and exception details from the source docstring."""
    source = inspect.getdoc(getattr(cls, method.name)) or ""
    sections = Docstring(source).parse(
        Parser.google, warn_unknown_params=False, warn_missing_types=False
    )
    blocks = []
    labels = {
        "parameters": "Parameters",
        "returns": "Returns",
        "yields": "Yields",
        "raises": "Raises",
    }
    for section in sections:
        kind = section.kind.value
        if kind == "text":
            blocks.append(reference_description(section.value))
        elif kind in labels:
            entries = []
            for entry in section.value:
                label = (
                    entry.name if kind == "parameters" else str(entry.annotation or "")
                )
                if label:
                    entries.append(
                        reference_row(
                            rx.el.p(
                                label,
                                class_name="m-0 font-mono text-sm font-medium leading-6 text-foreground [overflow-wrap:anywhere]",
                            ),
                            entry.description,
                        )
                    )
                else:
                    entries.append(reference_description(entry.description))
            blocks.append(
                rx.el.div(
                    rx.el.h4(
                        labels[kind],
                        class_name="m-0 text-sm font-medium leading-6 text-foreground",
                    ),
                    rx.el.div(
                        *entries,
                        class_name=(
                            "flex flex-col gap-2 [&>div]:border-0 [&>div]:py-0"
                            if kind in ("returns", "yields")
                            else "border-t border-border [&>div:last-child]:border-b-0"
                        ),
                    ),
                    class_name="flex flex-col gap-2",
                )
            )
    return blocks


def method_section(cls: type, method: MethodDocumentation) -> rx.Component:
    """Render a method with a full-width signature and structured documentation."""
    return rx.el.section(
        member_heading(method.name),
        rx.el.pre(
            rx.el.code(
                multiline_signature(method),
                class_name="font-mono text-[13px] leading-6",
            ),
            class_name="m-0 min-w-0 rounded-lg border border-border-subtle bg-accent p-4 text-foreground whitespace-pre-wrap [overflow-wrap:anywhere]",
        ),
        *method_details(cls, method),
        class_name="flex min-w-0 flex-col gap-4 border-t border-border py-6",
    )


def generate_class_reference(
    cls: type, env_var_prefix: str | None = None
) -> tuple[list[tuple[int, str]], rx.Component]:
    """Build a consistent class reference with navigation for all documented members."""
    doc = generate_class_documentation(cls)
    toc = []
    sections = []
    for title, fields in (("Class Fields", doc.class_fields), ("Fields", doc.fields)):
        if fields:
            toc.extend([(2, title), *((3, field.name) for field in fields)])
            sections.extend([
                h2_comp(text=title),
                rx.el.div(
                    *(field_row(field, env_var_prefix) for field in fields),
                    class_name="border-t border-border",
                ),
            ])
    if doc.methods:
        toc.extend([(2, "Methods"), *((3, method.name) for method in doc.methods)])
        sections.extend([
            h2_comp(text="Methods"),
            rx.el.div(*(method_section(cls, method) for method in doc.methods)),
        ])
    return toc, rx.el.div(
        h1_comp(text=cls.__name__),
        rx.el.p(doc.name, class_name="mb-5 font-mono text-sm text-muted-foreground"),
        render_markdown(doc.description or ""),
        *sections,
        class_name="min-w-0 api-reference-detail",
    )
