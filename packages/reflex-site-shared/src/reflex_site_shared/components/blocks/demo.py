"""Components for rendering code demos in the documentation."""

import textwrap
from typing import Any

import ruff_format

import reflex as rx

from .code import code_block, code_block_dark
from .tabs import doc_tab_card, doc_tab_list, doc_tab_trigger


def docdemobox(*children, **props) -> rx.Component:
    """Create a documentation demo box with the output of the code.

    Args:
        children: The children to display.
        props: Additional props to apply to the box.

    Returns:
        The styled demo box.
    """
    return rx.box(
        *children,
        **props,
        class_name="flex flex-col p-6 rounded-xl overflow-x-auto border border-secondary-4 bg-secondary-2 items-center justify-center w-full",
    )


def doccode(
    code: str,
    language: str = "python",
    lines: tuple[int, int] | None = None,
    theme: str = "light",
) -> rx.Component:
    """Create a documentation code snippet.

    Args:
        code: The code to display.
        language: The language of the code.
        lines: The start/end lines to display.
        theme: The theme for the code snippet.

    Returns:
        The styled code snippet.
    """
    # For Python snippets, lint the code with black.
    if language == "python":
        code = ruff_format.format_string(textwrap.dedent(code)).strip()

    # If needed, only display a subset of the lines.
    if lines is not None:
        code = textwrap.dedent(
            "\n".join(code.strip().splitlines()[lines[0] : lines[1]])
        ).strip()

    # Create the code snippet.
    cb = code_block_dark if theme == "dark" else code_block
    return cb(
        code=code,
        language=language,
    )


def _doc_view_panel(
    comp: rx.Component,
    demobox_props: dict[str, Any] | None = None,
) -> rx.Component:
    """Create a preview panel on the tab card's shared surface.

    Args:
        comp: Rendered demo component.
        demobox_props: Props to apply to the demo content wrapper.

    Returns:
        The styled preview panel.
    """
    return rx.tabs.content(
        rx.box(
            docdemobox(comp, **(demobox_props or {})),
            class_name=(
                "[&>div]:!rounded-none [&>div]:!border-0 [&>div]:!bg-transparent"
            ),
        ),
        value="view",
        class_name="w-full outline-none",
    )


def _doc_code_panel(
    source: str,
    value: str,
    theme: str = "light",
) -> rx.Component:
    """Create a code panel that uses the tab card's shared surface.

    Args:
        source: Source code to display.
        value: Value of the corresponding tab trigger.
        theme: Theme for the code snippet.

    Returns:
        The styled tab panel.
    """
    return rx.tabs.content(
        doccode(source, theme=theme),
        value=value,
        class_name=(
            "w-full p-4 outline-none sm:p-6 [&>div]:!m-0 "
            "[&>div]:!rounded-none [&>div]:!border-0 [&>div]:!bg-transparent "
            "[&_div]:!bg-transparent [&_pre]:!bg-transparent "
            "[&_.code-block]:!rounded-none [&_.code-block]:!border-0 "
            "[&_.code-block]:!bg-transparent [&_.code-block]:!shadow-none "
            "[&_summary]:!from-[var(--secondary-2)]"
        ),
    )


def docdemo(
    code: str,
    state: str | None = None,
    comp: rx.Component | None = None,
    context: bool = False,
    demobox_props: dict[str, Any] | None = None,
    theme: str | None = None,
    **props,
) -> rx.Component:
    """Create a documentation demo with code and output.

    Args:
        code: The code to render the component.
        state: Code for any state needed for the component.
        comp: The pre-rendered component.
        context: Whether to wrap the render code in a function.
        demobox_props: Props to apply to the demo box.
        theme: The theme for the code snippet.
        props: Additional props to apply to the component.

    Returns:
        The styled demo.
    """
    demobox_props = demobox_props or {}
    # Render the component if necessary.
    if comp is None:
        comp = eval(code)

    # Wrap the render code in a function if needed.
    if context:
        code = f"""def index():
        return {code}
        """

    # Add the state code
    if state is not None:
        code = state + code

    demobox_props.pop("toggle", None)
    return rx.box(
        rx.tabs.root(
            doc_tab_list(
                doc_tab_trigger("View", value="view", icon="eye"),
                doc_tab_trigger("Code", value="code", icon="code-xml"),
            ),
            doc_tab_card(
                _doc_view_panel(comp, demobox_props),
                _doc_code_panel(code, "code", theme or "light"),
            ),
            default_value="view",
            class_name="w-full",
        ),
        class_name="w-full py-4",
        **props,
    )


def docgraphing(
    code: str,
    comp: rx.Component | None = None,
    data: str | None = None,
) -> rx.Component:
    """Create a graph demo with connected code and data tabs.

    Args:
        code: Chart source code to display.
        comp: Rendered chart preview.
        data: Optional extracted chart data source.

    Returns:
        The styled graph demo.
    """
    tabs = [
        (
            doc_tab_trigger("View", value="view", icon="eye"),
            _doc_view_panel(comp),
        ),
        (
            doc_tab_trigger("Code", value="code", icon="code-xml"),
            _doc_code_panel(code, "code"),
        ),
    ]
    if data:
        tabs.append((
            doc_tab_trigger("Data", value="data", icon="database"),
            _doc_code_panel(data, "data"),
        ))

    return rx.box(
        rx.tabs.root(
            doc_tab_list(*(trigger for trigger, _ in tabs)),
            doc_tab_card(*(panel for _, panel in tabs)),
            default_value="view",
            class_name="w-full",
        ),
        class_name="w-full py-4 flex flex-col",
    )
