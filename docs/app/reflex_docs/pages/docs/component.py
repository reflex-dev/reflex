"""Utility functions for the component docs page."""

import hashlib
import os
import textwrap
from pathlib import Path
from types import UnionType
from typing import Literal, Union, _GenericAlias, get_args, get_origin

import reflex as rx
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
from reflex_docs.templates.docpage import docdemobox, docpage, h1_comp, h2_comp


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
]


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
            PropDocsState.add_var(name, bool, False)
            var = getattr(PropDocsState, name)
            PropDocsState._create_setter(name, var)
            setter = getattr(PropDocsState, f"set_{name}")
            prop_dict[prop.name] = var
            return rx.checkbox(
                var,
                on_change=setter,
            )
    except TypeError:
        pass

    if not isinstance(type_, _GenericAlias) or (
        type_.__origin__ not in (Literal, Union)
    ):
        return rx.fragment()
    # For the Union[Literal, Breakpoints] type
    if type_.__origin__ is Union:
        if not all(
            arg.__name__ in ["Literal", "Breakpoints"] for arg in type_.__args__
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
            return rx.select.root(
                rx.select.trigger(class_name="w-32 font-small text-slate-11"),
                rx.select.content(
                    rx.select.group(*[
                        rx.select.item(item, value=item, class_name="font-small")
                        for item in literal_values
                    ])
                ),
                value=var,
                on_change=setter,
            )
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
        return rx.popover.root(
            rx.popover.trigger(
                rx.box(
                    rx.button(
                        rx.text(var, class_name="font-small"),
                        # Match the select.trigger svg icon
                        rx.html(
                            """<svg width="9" height="9" viewBox="0 0 9 9" fill="currentcolor" xmlns="http://www.w3.org/2000/svg" class="rt-SelectIcon" aria-hidden="true"><path d="M0.135232 3.15803C0.324102 2.95657 0.640521 2.94637 0.841971 3.13523L4.5 6.56464L8.158 3.13523C8.3595 2.94637 8.6759 2.95657 8.8648 3.15803C9.0536 3.35949 9.0434 3.67591 8.842 3.86477L4.84197 7.6148C4.64964 7.7951 4.35036 7.7951 4.15803 7.6148L0.158031 3.86477C-0.0434285 3.67591 -0.0536285 3.35949 0.135232 3.15803Z"></path></svg>"""
                        ),
                        color_scheme=var,
                        variant="surface",
                        class_name="w-32 justify-between",
                    ),
                ),
            ),
            rx.popover.content(
                rx.grid(
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
                                var == color, "2px solid var(--gray-12)", ""
                            ),
                            class_name="relative shrink-0 rounded-md size-8 cursor-pointer",
                        )
                        for color in list(map(str, type_.__args__))
                        if color != ""
                    ],
                    columns="6",
                    spacing="3",
                ),
            ),
        )
    return rx.select.root(
        rx.select.trigger(class_name="font-small w-32 text-slate-11"),
        rx.select.content(
            rx.select.group(*[
                rx.select.item(
                    item,
                    value=item,
                    class_name="font-small",
                    _hover=(
                        {"background": f"var(--{item}-9)"}
                        if prop.name == "color_scheme"
                        else None
                    ),
                )
                for item in list(map(str, type_.__args__))
                if item != ""
            ]),
        ),
        value=var,
        on_change=setter,
    )


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
    prop_dict: dict,
    component: type[Component],
    is_interactive: bool,
) -> list[rx.Component]:
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
    # Return the docs for the prop.
    return [
        rx.table.cell(
            rx.box(
                rx.code(prop.name, class_name="code-style text-nowrap leading-normal"),
                hovercard(
                    rx.icon(
                        tag="info",
                        size=15,
                        class_name="!text-slate-9 shrink-0",
                    ),
                    rx.text(prop.description, class_name="font-small text-slate-11"),
                ),
                class_name="flex flex-row items-center gap-2",
            ),
            class_name="justify-start pl-4",
        ),
        rx.table.cell(
            rx.box(
                rx.cond(
                    (len(literal_values) > 0) & (prop.name not in common_types),
                    rx.code(
                        (
                            " | ".join(
                                [f'"{v}"' for v in literal_values[:max_prop_values]]
                                + ["..."]
                            )
                            if len(literal_values) > max_prop_values
                            else type_name
                        ),
                        style=get_code_style(color),
                        class_name="code-style text-nowrap leading-normal",
                    ),
                    rx.code(
                        type_name,
                        style=get_code_style(color),
                        class_name="code-style text-nowrap leading-normal",
                    ),
                ),
                rx.cond(
                    len(literal_values) > max_prop_values
                    and prop.name not in common_types,
                    hovercard(
                        rx.icon(
                            tag="circle-ellipsis",
                            size=15,
                            class_name="!text-slate-9 shrink-0",
                        ),
                        rx.text(
                            " | ".join([f'"{v}"' for v in literal_values]),
                            class_name="font-small text-slate-11",
                        ),
                    ),
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
                class_name="flex flex-row items-center gap-2",
            ),
            class_name="justify-start pl-4",
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
                class_name="flex",
            ),
            class_name="justify-start pl-4",
        ),
        rx.table.cell(
            render_select(prop, component, prop_dict),
            class_name="justify-start pl-4",
        )
        if is_interactive
        else rx.fragment(),
    ]


def generate_props(
    props: tuple[PropDocumentation, ...],
    component: type[Component],
    previews: dict[str, str],
) -> rx.Component:
    prop_list = list(props)
    if len(prop_list) == 0:
        return rx.box(
            rx.heading("Props", as_="h3", class_name="font-large text-slate-12"),
            rx.text("No component specific props", class_name="text-slate-9 font-base"),
            class_name="flex flex-col overflow-x-auto justify-start py-2 w-full",
        )

    table_header_class_name = (
        "font-small text-slate-12 text-normal w-auto justify-start pl-4 font-bold"
    )

    prop_dict = {}

    is_interactive = True
    if not issubclass(
        component, (RadixThemesComponent, RadixPrimitiveComponent)
    ) or component.__name__ in [
        "Theme",
        "ThemePanel",
        "DrawerRoot",
        "DrawerTrigger",
        "DrawerOverlay",
        "DrawerPortal",
        "DrawerContent",
        "DrawerClose",
    ]:
        is_interactive = False

    body = rx.table.body(
        *[
            rx.table.row(
                *prop_docs(prop, prop_dict, component, is_interactive), align="center"
            )
            for prop in prop_list
            if not prop.name.startswith("on_")  # ignore event trigger props
        ],
        class_name="bg-slate-2",
    )

    comp: rx.Component
    try:
        if component.__name__ in previews:
            comp = eval(previews[component.__name__])(**prop_dict)

        elif not is_interactive:
            comp = rx.fragment()

        else:
            try:
                comp = rx.vstack(component.create("Test", **prop_dict))
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

    interactive_component = (
        docdemobox(comp) if not isinstance(comp, Fragment) else "",
    )
    return rx.vstack(
        interactive_component,
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
                            "Prop",
                            class_name=table_header_class_name,
                        ),
                        rx.table.column_header_cell(
                            "Type | Values",
                            class_name=table_header_class_name,
                        ),
                        rx.table.column_header_cell(
                            "Default",
                            class_name=table_header_class_name,
                        ),
                        rx.table.column_header_cell(
                            "Interactive",
                            class_name=table_header_class_name,
                        )
                        if is_interactive
                        else rx.fragment(),
                    ),
                    class_name="bg-slate-3",
                ),
                body,
                variant="surface",
                size="1",
                class_name="px-0 w-full border border-slate-4",
            ),
            class_name="max-h-96 mb-4",
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
    props = generate_props(doc.props, component, previews)
    triggers = generate_event_triggers(doc.event_handlers)
    children = generate_valid_children(component)

    # Map for component display name overrides (e.g., for Python reserved keywords)
    component_display_name_map = {
        "rx.el.Del": "rx.el.del",
    }

    comp_display_name = component_display_name_map.get(
        component_tuple[1], component_tuple[1]
    )

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
    fname = path.strip("/") + ".md"
    ll_doc_exists = os.path.exists(fname.replace(".md", "-ll.md"))

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
        if component_list:
            toc.append((1, "API Reference"))
        for component_tuple in component_list[1:]:
            toc.append((2, component_tuple[1]))
        return (toc, doc_content), rx.box(
            links("hl", ll_doc_exists, path),
            render_docgen_document(
                virtual_filepath=virtual_path, actual_filepath=actual_path
            ),
            h1_comp(text="API Reference"),
            rx.box(*components, class_name="flex flex-col"),
            class_name="flex flex-col w-full",
        )

    @docpage(set_path=path + "low", t=title + " (Low Level)")
    def ll():
        ll_actual = fname.replace(".md", "-ll.md")
        ll_virtual = virtual_path.replace(".md", "-ll.md")
        toc = get_docgen_toc(ll_actual)
        doc_content = Path(ll_actual).read_text(encoding="utf-8")
        if component_list:
            toc.append((1, "API Reference"))
        for component_tuple in component_list[1:]:
            toc.append((2, component_tuple[1]))
        return (toc, doc_content), rx.box(
            links("ll", ll_doc_exists, path),
            render_docgen_document(
                virtual_filepath=ll_virtual, actual_filepath=ll_actual
            ),
            h1_comp(text="API Reference"),
            rx.box(*components, class_name="flex flex-col"),
            class_name="flex flex-col w-full",
        )

    if ll_doc_exists:
        return (out, ll)
    else:
        return out
