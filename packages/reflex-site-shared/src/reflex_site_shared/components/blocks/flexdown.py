"""Flexdown module — component maps and markdown helpers."""

# pyright: reportAttributeAccessIssue=false
from reflex_base.constants.colors import ColorType
from reflex_components_code.shiki_code_block import code_block as shiki_code_block

import reflex as rx
from reflex_site_shared.components.blocks.code import (
    code_block_markdown,
    code_block_markdown_dark,
)
from reflex_site_shared.components.blocks.headings import (
    h1_comp_xd,
    h2_comp_xd,
    h3_comp_xd,
    h4_comp_xd,
    img_comp_xd,
)
from reflex_site_shared.components.blocks.typography import (
    code_comp,
    doclink2,
    list_comp,
    ordered_list_comp,
    text_comp,
    unordered_list_comp,
)
from reflex_site_shared.styles.fonts import base, code


def get_code_style(color: ColorType):
    """Get code style.

    Returns:
        The component.
    """
    return {
        "p": {"margin_y": "0px"},
        "code": {
            "color": rx.color(color, 11),
            "border_radius": "4px",
            "border": f"1px solid {rx.color(color, 5)}",
            "background": rx.color(color, 4),
            **code,
        },
        **base,
    }


def _markdown_table(*children, **props) -> rx.Component:
    return rx.box(
        rx.el.table(
            *children,
            class_name="w-full border-collapse text-sm border border-secondary-4 rounded-lg overflow-hidden bg-white-1 ",
            **props,
        ),
        class_name="w-full rounded-xl border border-secondary-a4 my-6 max-w-full overflow-hidden",
    )


def _markdown_thead(*children, **props) -> rx.Component:
    return rx.el.thead(
        *children,
        class_name="bg-secondary-1 border-b border-secondary-4",
        **props,
    )


def _markdown_tbody(*children, **props) -> rx.Component:
    return rx.el.tbody(
        *children,
        class_name="[&_tr:nth-child(even)]:bg-secondary-1",
        **props,
    )


def _markdown_tr(*children, **props) -> rx.Component:
    return rx.el.tr(
        *children,
        class_name="border-b border-secondary-4 last:border-b-0",
        **props,
    )


def _markdown_th(*children, **props) -> rx.Component:
    return rx.el.th(
        *children,
        class_name="px-3 py-2.5 text-left text-xs font-[575] text-secondary-12 align-top",
        **props,
    )


def _markdown_td(*children, **props) -> rx.Component:
    return rx.el.td(
        *children,
        class_name="px-3 py-2.5 text-xs font-medium first:font-[575] text-secondary-11 align-top",
        **props,
    )


_markdown_table_component_map: dict[str, object] = {
    "table": _markdown_table,
    "thead": _markdown_thead,
    "tbody": _markdown_tbody,
    "tr": _markdown_tr,
    "th": _markdown_th,
    "td": _markdown_td,
}

component_map = {
    "h1": lambda text: h1_comp_xd(text=text),
    "h2": lambda text: h2_comp_xd(text=text),
    "h3": lambda text: h3_comp_xd(text=text),
    "h4": lambda text: h4_comp_xd(text=text),
    "p": lambda text: text_comp(text=text),
    "li": lambda text: list_comp(text=text),
    "a": doclink2,
    "code": lambda text: code_comp(text=text),
    "pre": code_block_markdown,
    "img": lambda src: img_comp_xd(src=src),
    **_markdown_table_component_map,
}
comp2 = component_map.copy()
comp2["pre"] = code_block_markdown_dark
comp2["ul"] = lambda items: unordered_list_comp(items=items)
comp2["ol"] = lambda items: ordered_list_comp(items=items)


def markdown(text: str):
    """Markdown.

    Returns:
        The component.
    """
    return rx.markdown(text, component_map=component_map)


def markdown_codeblock(value: str, **props: object) -> rx.Component:
    """Render a code block using the Shiki-based code block component.

    Returns:
        The component.
    """
    return shiki_code_block(value, **props)


def markdown_with_shiki(*args, **kwargs):
    """Wrapper for the markdown component with a customized component map.
    Uses the Shiki-based code block
    instead of the default CodeBlock component for code blocks.

    Note: This wrapper should be removed once the default codeblock
    in rx.markdown component map is updated to the Shiki-based code block.

    Returns:
            The component.
    """
    return rx.markdown(
        *args,
        component_map={
            "h1": lambda text: h1_comp_xd(text=text),
            "h2": lambda text: h2_comp_xd(text=text),
            "h3": lambda text: h3_comp_xd(text=text),
            "h4": lambda text: h4_comp_xd(text=text),
            "p": lambda text: text_comp(text=text),
            "li": lambda text: list_comp(text=text),
            "a": doclink2,
            "pre": markdown_codeblock,
            "img": lambda src: img_comp_xd(src=src),
        },
        **kwargs,
    )
