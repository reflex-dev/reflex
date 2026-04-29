"""Utility functions for the component docs page."""

import hashlib
import os
import re
import textwrap
from pathlib import Path
from types import UnionType
from typing import Literal, Union, _GenericAlias, get_args, get_origin

import reflex as rx
import reflex_components_internal as ui
from reflex.components.base.fragment import Fragment
from reflex.components.component import Component
from reflex.components.radix.primitives.base import RadixPrimitiveComponent
from reflex.components.radix.themes.base import RadixThemesComponent
from reflex_docgen import (
    EventHandlerDocumentation,
    PropDocumentation,
    generate_documentation,
)

from reflex_docs.docgen_pipeline import (
    get_docgen_toc,
    render_docgen_document,
    render_markdown,
)
from reflex_docs.templates.docpage import docpage, h1_comp, h2_comp


def get_code_style(color: str):
    return {
        "color": rx.color(color, 11),
        "border_radius": "0.25rem",
        "border": f"1px solid {rx.color(color, 5)}",
        "background": rx.color(color, 3),
    }


# Mapping from types to colors.
TYPE_COLORS = {
    "int": "red",
    "float": "orange",
    "str": "yellow",
    "bool": "teal",
    "Component": "purple",
    "List": "blue",
    "Dict": "blue",
    "Tuple": "blue",
    "None": "gray",
    "Figure": "green",
    "Literal": "gray",
    "Union": "gray",
}

count = 0


def get_id(s):
    global count
    count += 1
    s = str(count)
    hash_object = hashlib.sha256(s.encode())
    hex_dig = hash_object.hexdigest()
    return "a_" + hex_dig[:8]


class PropDocsState(rx.State):
    """Container for dynamic vars used by the prop docs."""


EXCLUDED_COMPONENTS = [
    "Theme",
    "ThemePanel",
    "DrawerRoot",
    "DrawerTrigger",
    "DrawerOverlay",
    "DrawerPortal",
    "DrawerContent",
    "DrawerClose",
    "Container",
    "Spacer",
    "Skeleton",
    "Section",
    "Tooltip",
]


_PILL_BTN_CLASS = (
    "text-sm font-medium cursor-pointer rounded-md px-2.5 py-1 text-secondary-11 "
    "border border-secondary-5 bg-secondary-1 hover:bg-secondary-3 transition-colors"
)
_PILL_BTN_ACTIVE_CLASS = (
    "text-sm font-medium cursor-pointer rounded-md px-2.5 py-1 text-secondary-12 "
    "border border-secondary-8 bg-secondary-4"
)


def _pill_button(label: str, active, on_click) -> rx.Component:
    return rx.el.button(
        label,
        type="button",
        on_click=on_click,
        class_name=rx.cond(active, _PILL_BTN_ACTIVE_CLASS, _PILL_BTN_CLASS),
    )


def _pill_row(values, var, setter) -> rx.Component:
    return rx.box(
        *[_pill_button(v, var == v, setter(v)) for v in values],
        class_name="flex flex-wrap gap-1.5",
    )


def _bool_pills(var, setter) -> rx.Component:
    return rx.box(
        _pill_button("false", ~var, setter(False)),
        _pill_button("true", var, setter(True)),
        class_name="flex flex-wrap gap-1.5",
    )


def render_select(prop: PropDocumentation, component: type[Component], prop_dict: dict):
    if (
        not safe_issubclass(component, (RadixThemesComponent, RadixPrimitiveComponent))
        or component.__name__ in EXCLUDED_COMPONENTS
    ):
        return rx.fragment()
    try:
        type_ = get_args(prop.type)[0]
    except Exception:
        return rx.fragment()

    try:
        if issubclass(type_, bool) and prop.name not in [
            "open",
            "checked",
            "as_child",
            "default_open",
            "default_checked",
        ]:
            name = get_id(f"{component.__qualname__}_{prop.name}")
            default = prop.name == "loading" and component.__name__ == "Spinner"
            PropDocsState.add_var(name, bool, default)
            var = getattr(PropDocsState, name)
            PropDocsState._create_setter(name, var)
            setter = getattr(PropDocsState, f"set_{name}")
            prop_dict[prop.name] = var
            return _bool_pills(var, setter)
    except TypeError:
        pass

    type_origin = get_origin(type_)
    if not isinstance(type_, (_GenericAlias, UnionType)) or (
        type_origin not in (Literal, Union, UnionType)
    ):
        return rx.fragment()
    # For the Union[Literal, Breakpoints] type
    if type_origin in (Union, UnionType):
        if not all(
            getattr(arg, "__name__", "") in ["Literal", "Breakpoints"]
            for arg in type_.__args__
        ):
            return rx.fragment()
        else:
            # Get the literal values
            literal_values = [
                str(lit_arg)
                for arg in type_.__args__
                if get_origin(arg) is Literal
                for lit_arg in arg.__args__
                if str(lit_arg) != ""
            ]
            option = literal_values[0]
            name = get_id(f"{component.__qualname__}_{prop.name}")
            PropDocsState.add_var(name, str, option)
            var = getattr(PropDocsState, name)
            PropDocsState._create_setter(name, var)
            setter = getattr(PropDocsState, f"set_{name}")
            prop_dict[prop.name] = var
            return _pill_row(literal_values, var, setter)
    # Get the first non-empty option.
    non_empty_args = [a for a in type_.__args__ if str(a) != ""]
    option = non_empty_args[0] if non_empty_args else type_.__args__[0]
    name = get_id(f"{component.__qualname__}_{prop.name}")
    PropDocsState.add_var(name, str, option)
    var = getattr(PropDocsState, name)
    PropDocsState._create_setter(name, var)
    setter = getattr(PropDocsState, f"set_{name}")
    prop_dict[prop.name] = var

    if prop.name == "color_scheme":
        return ui.popover(
            trigger=rx.button(
                rx.text(var, class_name="text-sm font-medium"),
                ui.icon("ArrowDown01Icon"),
                color_scheme=var,
                variant="surface",
                class_name="w-32 justify-between cursor-pointer",
            ),
            content=rx.box(
                *[
                    rx.box(
                        rx.icon(
                            "check",
                            size=15,
                            display=rx.cond(var == color, "block", "none"),
                            class_name="text-gray-12 absolute top-1/2 left-1/2 translate-x-[-50%] translate-y-[-50%]",
                        ),
                        bg=f"var(--{color}-9)",
                        on_click=PropDocsState.setvar(f"{name}", color),
                        border=rx.cond(
                            var == color,
                            "2px solid var(--gray-12)",
                            "2px solid transparent",
                        ),
                        class_name="relative shrink-0 rounded-md size-8 cursor-pointer box-border",
                    )
                    for color in list(map(str, type_.__args__))
                    if color != ""
                ],
                class_name="grid grid-cols-[repeat(6,2rem)] gap-3 p-3",
            ),
            align="start",
            class_name="w-fit",
        )
    literal_values = [str(a) for a in type_.__args__ if str(a) != ""]
    return _pill_row(literal_values, var, setter)


def hovercard(trigger: rx.Component, content: rx.Component) -> rx.Component:
    return rx.hover_card.root(
        rx.hover_card.trigger(
            trigger,
        ),
        rx.hover_card.content(
            content, side="top", align="center", class_name="font-small text-slate-11"
        ),
    )


def color_scheme_hovercard(literal_values: list[str]) -> rx.Component:
    return hovercard(
        rx.icon(tag="palette", size=15, class_name="!text-slate-9 shrink-0"),
        rx.grid(
            *[
                rx.tooltip(
                    rx.box(
                        bg=f"var(--{color}-9)", class_name="rounded-md size-8 shrink-0"
                    ),
                    content=color,
                    delay_duration=0,
                )
                for color in literal_values
            ],
            columns="6",
            spacing="3",
        ),
    )


def safe_issubclass(cls, class_or_tuple):
    try:
        return issubclass(cls, class_or_tuple)
    except TypeError:
        return False


def prop_docs(
    prop: PropDocumentation,
    component: type[Component],
) -> tuple[list[rx.Component], bool]:
    """Generate the docs for a prop."""
    # Get the type of the prop.
    type_ = prop.type
    origin = get_origin(type_)
    if safe_issubclass(origin, rx.Var):
        # For vars, get the type of the var.
        type_ = get_args(type_)[0]

    origin = get_origin(type_)
    args = get_args(type_)

    literal_values = []  # Literal values of the prop
    all_types = []  # List for all the prop types
    max_prop_values = 2

    short_type_name = None

    common_types = {}  # Used to exclude common types from the max_prop_values
    if origin in (Union, UnionType):
        non_literal_types = []  # List for all the non-literal types

        for arg in args:
            all_types.append(arg.__name__)
            if get_origin(arg) is Literal:
                literal_values.extend(str(lit_arg) for lit_arg in arg.__args__)
            elif arg.__name__ != "Breakpoints":  # Don't include Breakpoints
                non_literal_types.append(arg.__name__)

        if len(literal_values) < 10:
            literal_str = " | ".join(f'"{value}"' for value in literal_values)
            type_components = ([literal_str] if literal_str else []) + non_literal_types
            type_name = (
                " | ".join(type_components)
                if len(type_components) == 1
                else f"Union[{', '.join(type_components)}]"
            )
        else:
            type_name = (
                "Literal"
                if not non_literal_types
                else f"Union[Literal, {', '.join(non_literal_types)}]"
            )

        short_type_name = "Union"

    elif origin is dict:
        key_type = args[0].__name__ if args else "Any"
        value_type = (
            getattr(args[1], "__name__", str(args[1])) if len(args) > 1 else "Any"
        )
        type_name = f"Dict[{key_type}, {value_type}]"
        short_type_name = "Dict"

    elif origin is Literal:
        literal_values = list(map(str, args))
        if len(literal_values) > max_prop_values and prop.name not in common_types:
            type_name = "Literal"
        else:
            type_name = " | ".join([f'"{value}"' for value in literal_values])
        short_type_name = "Literal"

    else:
        type_name = type_.__name__
        short_type_name = type_name

    # Get the default value.
    default_value = prop.default_value if prop.default_value is not None else "-"
    # Get the color of the prop.
    color = TYPE_COLORS.get(short_type_name, "gray")

    description = prop.description or ""
    is_long_row = len(description) > 160 or (
        literal_values and len(literal_values) > 8 and prop.name not in common_types
    )

    cell_content_class = (
        (
            "cell-content max-h-[6.5em] overflow-hidden "
            "[mask-image:linear-gradient(to_bottom,black_85%,transparent)] "
            "[-webkit-mask-image:linear-gradient(to_bottom,black_85%,transparent)]"
        )
        if is_long_row
        else "cell-content"
    )

    # Return the docs for the prop.
    return [
        rx.table.cell(
            rx.box(
                rx.code(prop.name, class_name="code-style text-nowrap leading-normal"),
                class_name=cell_content_class,
            ),
            class_name="justify-start pl-4 align-top py-3",
        ),
        rx.table.cell(
            rx.box(
                rx.box(
                    rx.box(
                        *(
                            [
                                rx.code(
                                    f'"{v}"',
                                    color_scheme=color,
                                    variant="soft",
                                    class_name="code-style leading-normal text-nowrap",
                                )
                                for v in literal_values
                            ]
                            if literal_values and prop.name not in common_types
                            else [
                                rx.code(
                                    type_name,
                                    color_scheme=color,
                                    variant="soft",
                                    class_name="code-style leading-normal whitespace-normal break-words",
                                )
                            ]
                        ),
                        class_name="flex flex-wrap gap-1",
                    ),
                    class_name=cell_content_class,
                ),
                rx.cond(
                    (origin == Union)
                    & (
                        "Breakpoints" in all_types
                    ),  # Display that the type is Union with Breakpoints
                    hovercard(
                        rx.icon(
                            tag="info",
                            size=15,
                            class_name="!text-slate-9 shrink-0",
                        ),
                        rx.text(
                            f"Union[{', '.join(all_types)}]",
                            class_name="font-small text-slate-11",
                        ),
                    ),
                ),
                rx.cond(
                    (prop.name == "color_scheme") | (prop.name == "accent_color"),
                    color_scheme_hovercard(literal_values),
                ),
                class_name="flex flex-row items-start gap-2",
            ),
            class_name="justify-start pl-4 align-top py-3",
        ),
        rx.table.cell(
            rx.box(
                rx.code(
                    default_value,
                    style=get_code_style(
                        "red"
                        if default_value == "False"
                        else "green"
                        if default_value == "True"
                        else "gray"
                    ),
                    class_name="code-style leading-normal text-nowrap",
                ),
                class_name=cell_content_class,
            ),
            class_name="justify-start pl-4 align-top py-3",
        ),
        rx.table.cell(
            rx.box(
                rx.text(
                    description,
                    class_name="font-small text-slate-11 whitespace-normal leading-snug break-words",
                ),
                class_name=cell_content_class,
            ),
            class_name="justify-start pl-4 align-top py-3 w-full",
        ),
    ], is_long_row


def generate_props(
    props: tuple[PropDocumentation, ...],
    component: type[Component],
    previews: dict[str, str],
    display_name: str | None = None,
) -> rx.Component:
    prop_list = list(props)
    if len(prop_list) == 0:
        return rx.box(
            rx.heading("Props", as_="h3", class_name="font-large text-slate-12"),
            rx.text("No component specific props", class_name="text-slate-9 font-base"),
            class_name="flex flex-col overflow-x-auto justify-start py-2 w-full",
        )

    table_header_class_name = (
        "text-xs text-secondary-11 w-auto justify-start pl-4 font-semibold capitalize"
    )

    prop_dict = {}

    is_interactive = True
    if (
        not issubclass(component, (RadixThemesComponent, RadixPrimitiveComponent))
        or component.__name__ in EXCLUDED_COMPONENTS
    ):
        is_interactive = False

    styling_props = {
        "variant",
        "size",
        "color_scheme",
        "radius",
        "high_contrast",
        "loading",
        "disabled",
        "weight",
        "align",
        "justify",
        "direction",
        "orientation",
    }

    # Props that a specific component visually ignores (e.g. CSS overrides
    # or deprecated HTML attributes), so we hide them from the interactive
    # controls to avoid confusion.
    per_component_skip = {
        "Center": {"align", "justify"},
        "TableRoot": {"align"},
        "TableCell": {"align"},
        "TableRowHeaderCell": {"align"},
        "TableColumnHeaderCell": {"align"},
        "AccordionRoot": {"orientation"},
        "SegmentedControlRoot": {"color_scheme"},
    }
    skip_props = per_component_skip.get(component.__name__, set())

    interactive_controls: list[tuple[PropDocumentation, rx.Component]] = []
    if is_interactive:
        for prop in prop_list:
            if prop.name.startswith("on_"):
                continue
            if prop.name not in styling_props or prop.name in skip_props:
                continue
            control = render_select(prop, component, prop_dict)
            if not isinstance(control, Fragment):
                interactive_controls.append((prop, control))

    def _toggle_row() -> rx.Component:
        return rx.el.tr(
            rx.el.td(
                rx.el.details(
                    rx.el.summary(
                        rx.el.span(
                            "Show more",
                            rx.icon(
                                "chevron-down",
                                size=12,
                                class_name="inline-block align-[-2px] ml-1",
                            ),
                            class_name="group-open/details:hidden",
                        ),
                        rx.el.span(
                            "Show less",
                            rx.icon(
                                "chevron-up",
                                size=12,
                                class_name="inline-block align-[-2px] ml-1",
                            ),
                            class_name="hidden group-open/details:inline",
                        ),
                        class_name=(
                            "block list-none cursor-pointer text-center text-xs "
                            "font-medium text-slate-11 hover:text-slate-12 py-2 "
                            "[&::-webkit-details-marker]:hidden [&::marker]:hidden"
                        ),
                    ),
                    class_name="group/details",
                ),
                col_span=4,
                class_name=(
                    "!p-0 !border-t-0 [box-shadow:0_-1px_0_0_var(--gray-a4)_inset]"
                ),
            ),
            class_name="api-toggle-row bg-slate-2",
        )

    data_row_class = (
        "[&:has(+_tr.api-toggle-row_details[open])_.cell-content]:!max-h-none "
        "[&:has(+_tr.api-toggle-row_details[open])_.cell-content]:!overflow-visible "
        "[&:has(+_tr.api-toggle-row_details[open])_.cell-content]:![mask-image:none] "
        "[&:has(+_tr.api-toggle-row_details[open])_.cell-content]:![-webkit-mask-image:none] "
        "[&>td]:!shadow-none"
    )

    rows: list[rx.Component] = []
    for prop in prop_list:
        if prop.name.startswith("on_"):  # ignore event trigger props
            continue
        cells, is_long_row = prop_docs(prop, component)
        rows.append(
            rx.table.row(
                *cells,
                align="center",
                class_name=data_row_class if is_long_row else "",
            )
        )
        if is_long_row:
            rows.append(_toggle_row())

    body = rx.table.body(*rows, class_name="bg-slate-2")

    comp: rx.Component
    try:
        if component.__name__ in previews:
            comp = eval(previews[component.__name__])(**prop_dict)

        elif not is_interactive:
            comp = rx.fragment()

        else:
            try:
                comp = rx.vstack(component.create("Preview", **prop_dict))
            except Exception:
                comp = rx.fragment()
            if "data" in component.__name__.lower():
                print(
                    "Data components cannot be created without a data source. Skipping interactive example."
                )
                comp = rx.fragment()
    except Exception as e:
        print(f"Failed to create component {component.__name__}, error: {e}")
        comp = rx.fragment()

    if not isinstance(comp, Fragment) and interactive_controls:
        component_call = display_name or f"rx.{component.__name__.lower()}"
        highlighted = {
            "variant",
            "size",
            "color_scheme",
            "radius",
            "high_contrast",
            "loading",
            "disabled",
            "weight",
            "align",
            "justify",
            "direction",
            "orientation",
        }
        bool_excluded = {
            "open",
            "checked",
            "as_child",
            "default_open",
            "default_checked",
        }

        def _is_bool_prop(p: PropDocumentation) -> bool:
            try:
                inner = get_args(p.type)[0]
                return safe_issubclass(inner, bool) and p.name not in bool_excluded
            except Exception:
                return False

        line_class = "font-mono text-sm whitespace-pre"
        kw_class = "text-violet-11"
        str_class = "text-orange-11"
        bool_class = "text-blue-11"
        prop_name_class = "text-slate-12"
        token_re = re.compile(
            r'(rx\.[\w.]+)|("[^"]*")|(\b(?:True|False|None)\b)|(\b\d+(?:\.\d+)?\b)|(\w+)|(\s+)|(.)'
        )

        def _render_static_line(line: str) -> rx.Component:
            if not line.strip():
                return rx.el.div(class_name=line_class + " min-h-[1em]")
            children: list = []
            for m in token_re.finditer(line):
                kw, s, b, n, ident, ws, other = m.groups()
                if kw is not None:
                    children.append(rx.el.span(kw, class_name=kw_class))
                elif s is not None:
                    children.append(rx.el.span(s, class_name=str_class))
                elif b is not None:
                    children.append(rx.el.span(b, class_name=bool_class))
                elif n is not None:
                    children.append(rx.el.span(n, class_name=bool_class))
                elif ident is not None:
                    children.append(ident)
                elif ws is not None:
                    children.append(ws)
                else:
                    children.append(other)
            return rx.el.div(*children, class_name=line_class)

        def _py_bool(var):
            return rx.cond(var, "True", "False")

        def _render_dynamic_prop(indent: str, p, var) -> rx.Component:
            if _is_bool_prop(p):
                return rx.el.div(
                    indent,
                    rx.el.span(p.name, class_name=prop_name_class),
                    "=",
                    rx.el.span(_py_bool(var), class_name=bool_class),
                    ",",
                    class_name=line_class,
                )
            return rx.el.div(
                indent,
                rx.el.span(p.name, class_name=prop_name_class),
                "=",
                rx.el.span('"', var, '"', class_name=str_class),
                ",",
                class_name=line_class,
            )

        preview_source = previews.get(component.__name__, "")
        code_children: list[rx.Component] = []
        used_preview = False

        if preview_source:
            src = preview_source.strip()
            m = re.match(r"^lambda\s+\*\*props\s*:\s*", src)
            if m:
                src = src[m.end() :]
            src = textwrap.dedent(src).rstrip()
            for line in src.split("\n"):
                if "**props" not in line:
                    code_children.append(_render_static_line(line))
                    continue
                # Split the line around the **props token.
                match = re.search(r"\*\*props\s*,?\s*", line)
                before = line[: match.start()] if match else line
                after = line[match.end() :] if match else ""
                base_indent = len(line) - len(line.lstrip())
                inline = bool(before.strip())
                # Compute prop-line indent: 4 deeper than the line's own
                # indent when the **props was inline; otherwise reuse the
                # line's indent (multi-line preview format).
                prop_indent = " " * (base_indent + 4 if inline else base_indent)
                if inline:
                    trimmed_before = before.rstrip()
                    if not trimmed_before.endswith(","):
                        trimmed_before += ","
                    code_children.append(_render_static_line(trimmed_before))
                for p, _ in interactive_controls:
                    if p.name not in highlighted:
                        continue
                    var = prop_dict.get(p.name)
                    if var is None:
                        continue
                    code_children.append(_render_dynamic_prop(prop_indent, p, var))
                trimmed_after = after.lstrip(", \t")
                if inline and trimmed_after.strip():
                    closing_indent = " " * base_indent
                    code_children.append(
                        _render_static_line(closing_indent + trimmed_after)
                    )
            used_preview = True

        if not used_preview:
            code_children.append(
                rx.el.div(
                    rx.el.span(component_call, class_name=kw_class),
                    "(",
                    class_name=line_class,
                )
            )
            for p, _ in interactive_controls:
                if p.name not in highlighted:
                    continue
                var = prop_dict.get(p.name)
                if var is None:
                    continue
                code_children.append(_render_dynamic_prop("    ", p, var))
            code_children.append(rx.el.div(")", class_name=line_class))

        interactive_component = rx.box(
            rx.box(
                comp,
                class_name=(
                    "flex flex-col items-center justify-center p-6 flex-1 "
                    "bg-slate-2 border-b lg:border-b-0 lg:border-r "
                    "border-slate-4 min-w-0"
                ),
            ),
            rx.box(
                *code_children,
                class_name="flex-1 p-4 bg-slate-1 min-w-0 overflow-x-auto",
            ),
            class_name=(
                "flex flex-col lg:flex-row w-full rounded-xl border "
                "border-slate-4 overflow-hidden"
            ),
        )
    else:
        interactive_component = rx.fragment()

    controls_panel: rx.Component = rx.fragment()
    if not isinstance(comp, Fragment) and interactive_controls:
        controls_panel = rx.box(
            *[
                rx.box(
                    rx.code(
                        prop.name,
                        class_name="code-style text-nowrap leading-normal text-slate-11",
                    ),
                    control,
                    class_name="grid grid-cols-[8rem_1fr] gap-4 items-start",
                )
                for prop, control in interactive_controls
            ],
            class_name="flex flex-col gap-3 border border-secondary-4 rounded-md p-4 bg-secondary-1 mb-4 w-full",
        )

    return rx.vstack(
        interactive_component,
        controls_panel,
        rx.heading(
            "Props",
            as_="h3",
            class_name="font-large text-slate-12 mt-4 mb-2 text-left self-start",
        ),
        rx.box(
            rx.table.root(
                rx.el.style(
                    """
                    .rt-TableRoot:where(.rt-variant-surface) :where(.rt-TableRootTable) :where(.rt-TableHeader) {
                    --table-row-background-color: "transparent"
                    }
                    """
                ),
                rx.table.header(
                    rx.table.row(
                        rx.table.column_header_cell(
                            "prop",
                            class_name=ui.cn(table_header_class_name, "w-[9rem]"),
                        ),
                        rx.table.column_header_cell(
                            "type",
                            class_name=ui.cn(table_header_class_name, "w-[34rem]"),
                        ),
                        rx.table.column_header_cell(
                            "default",
                            class_name=ui.cn(table_header_class_name, "w-[4rem]"),
                        ),
                        rx.table.column_header_cell(
                            "description",
                            class_name=ui.cn(table_header_class_name, "w-[18rem]"),
                        ),
                    ),
                    class_name="bg-secondary-2",
                ),
                body,
                variant="surface",
                size="1",
                class_name="px-0 border border-slate-4 w-full",
            ),
            class_name="mb-4 w-full overflow-hidden",
        ),
    )


def generate_event_triggers(
    handlers: tuple[EventHandlerDocumentation, ...],
) -> rx.Component:
    custom_handlers = [h for h in handlers if not h.is_inherited]

    if not custom_handlers:
        return rx.box(
            rx.heading(
                "Event Triggers", as_="h3", class_name="font-large text-slate-12"
            ),
            rx.link(
                "See the full list of default event triggers",
                href="https://reflex.dev/docs/api-reference/event-triggers/",
                class_name="text-violet-11 font-base",
                is_external=True,
            ),
            class_name="py-2 overflow-x-auto justify-start flex flex-col gap-4",
        )
    table_header_class_name = (
        "font-small text-slate-12 text-normal w-auto justify-start pl-4 font-bold"
    )
    return rx.box(
        rx.heading("Event Triggers", as_="h3", class_name="font-large text-slate-12"),
        rx.link(
            "See the full list of default event triggers",
            href="https://reflex.dev/docs/api-reference/event-triggers/",
            class_name="text-violet-11 font-base",
            is_external=True,
        ),
        rx.scroll_area(
            rx.table.root(
                rx.el.style(
                    """
                    .rt-TableRoot:where(.rt-variant-surface) :where(.rt-TableRootTable) :where(.rt-TableHeader) {
                        --table-row-background-color: "transparent"
                    }
                """
                ),
                rx.table.header(
                    rx.table.row(
                        rx.table.column_header_cell(
                            "Trigger", class_name=table_header_class_name
                        ),
                        rx.table.column_header_cell(
                            "Description", class_name=table_header_class_name
                        ),
                    ),
                    class_name="bg-slate-3",
                ),
                rx.table.body(
                    *[
                        rx.table.row(
                            rx.table.cell(
                                rx.code(handler.name, class_name="code-style"),
                                class_name="justify-start p-4",
                            ),
                            rx.table.cell(
                                handler.description or "",
                                class_name="justify-start p-4 text-slate-11 font-small",
                            ),
                        )
                        for handler in custom_handlers
                    ],
                    class_name="bg-slate-2",
                ),
                variant="surface",
                size="1",
                class_name="w-full border border-slate-4",
            ),
            class_name="w-full justify-start overflow-hidden",
        ),
        class_name="pb-6 w-full justify-start flex flex-col gap-6 max-h-[40rem]",
    )


def generate_valid_children(comp: type[Component]) -> rx.Component:
    if not comp._valid_children:
        return rx.text("")

    valid_children = [
        rx.code(child, class_name="code-style leading-normal")
        for child in comp._valid_children
    ]
    return rx.box(
        rx.heading("Valid Children", as_="h3", class_name="font-large text-slate-12"),
        rx.box(*valid_children, class_name="flex flex-row gap-2 flex-wrap"),
        class_name="pb-6 w-full items-start flex flex-col gap-4",
    )


def component_docs(
    component_tuple: tuple[type[Component], str], previews: dict[str, str]
) -> rx.Component:
    """Generates documentation for a given component."""
    component = component_tuple[0]
    doc = generate_documentation(component)

    # Map for component display name overrides (e.g., for Python reserved keywords)
    component_display_name_map = {
        "rx.el.Del": "rx.el.del",
    }

    comp_display_name = component_display_name_map.get(
        component_tuple[1], component_tuple[1]
    )

    props = generate_props(doc.props, component, previews, comp_display_name)
    triggers = generate_event_triggers(doc.event_handlers)
    children = generate_valid_children(component)

    return rx.box(
        h2_comp(text=comp_display_name),
        rx.box(
            render_markdown(textwrap.dedent(doc.description or "")), class_name="pb-2"
        ),
        props,
        children,
        triggers,
        class_name="pb-8 w-full text-left",
    )


def multi_docs(
    path: str,
    virtual_path: str,
    actual_path: str,
    previews: dict[str, str],
    component_list: list,
    title: str,
):
    components = [
        component_docs(component_tuple, previews)
        for component_tuple in component_list[1:]
    ]
    ll_actual_path = actual_path.replace(".md", "-ll.md")
    ll_doc_exists = os.path.exists(ll_actual_path)

    active_class_name = "font-small bg-slate-2 p-2 text-slate-11 rounded-xl shadow-large w-28 cursor-default border border-slate-4 text-center"

    non_active_class_name = "font-small w-28 transition-color hover:text-slate-11 text-slate-9 p-2 text-center"

    def links(current_page, ll_doc_exists, path):
        path = str(path).rstrip("/")
        if ll_doc_exists:
            if current_page == "hl":
                return rx.box(
                    rx.box(class_name="flex-grow"),
                    rx.box(
                        rx.link(
                            rx.box(rx.text("High Level"), class_name=active_class_name),
                            underline="none",
                        ),
                        rx.link(
                            rx.box(
                                rx.text("Low Level"), class_name=non_active_class_name
                            ),
                            href=path + "/low",
                            underline="none",
                        ),
                        class_name="bg-slate-3 rounded-[1.125rem] p-2 gap-2 flex items-center justify-center",
                    ),
                    class_name="flex mb-2",
                )
            else:
                return rx.box(
                    rx.box(class_name="flex-grow"),
                    rx.flex(
                        rx.link(
                            rx.box(
                                rx.text("High Level"), class_name=non_active_class_name
                            ),
                            href=path,
                            underline="none",
                        ),
                        rx.link(
                            rx.box(rx.text("Low Level"), class_name=active_class_name),
                            href=path + "/low",
                            underline="none",
                        ),
                        class_name="bg-slate-3 rounded-[1.125rem] p-2 gap-2 flex items-center justify-center",
                    ),
                    class_name="flex mb-2",
                )
        return rx.fragment()

    @docpage(set_path=path, t=title)
    def out():
        toc = get_docgen_toc(actual_path)
        doc_content = Path(actual_path).read_text(encoding="utf-8")
        # Append API Reference headings for the component list
        if components:
            toc.append((1, "API Reference"))
        for component_tuple in component_list[1:]:
            toc.append((2, component_tuple[1]))
        api_ref_section = (
            [
                h1_comp(text="API Reference"),
                rx.box(*components, class_name="flex flex-col"),
            ]
            if components
            else []
        )
        return (toc, doc_content), rx.box(
            links("hl", ll_doc_exists, path),
            render_docgen_document(
                virtual_filepath=virtual_path, actual_filepath=actual_path
            ),
            *api_ref_section,
            class_name="flex flex-col w-full",
        )

    @docpage(set_path=path + "low", t=title + " (Low Level)")
    def ll():
        ll_virtual = virtual_path.replace(".md", "-ll.md")
        toc = get_docgen_toc(ll_actual_path)
        doc_content = Path(ll_actual_path).read_text(encoding="utf-8")
        if components:
            toc.append((1, "API Reference"))
        for component_tuple in component_list[1:]:
            toc.append((2, component_tuple[1]))
        api_ref_section = (
            [
                h1_comp(text="API Reference"),
                rx.box(*components, class_name="flex flex-col"),
            ]
            if components
            else []
        )
        return (toc, doc_content), rx.box(
            links("ll", ll_doc_exists, path),
            render_docgen_document(
                virtual_filepath=ll_virtual, actual_filepath=ll_actual_path
            ),
            *api_ref_section,
            class_name="flex flex-col w-full",
        )

    if ll_doc_exists:
        return (out, ll)
    else:
        return out
