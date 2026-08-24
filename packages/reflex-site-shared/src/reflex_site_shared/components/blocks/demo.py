"""Components for rendering code demos in the documentation."""

import textwrap
from typing import Any

import reflex_components_internal as ui
import ruff_format

import reflex as rx
from reflex_site_shared.constants import REFLEX_BUILD_URL

from .code import code_block, code_block_dark
from .tabs import doc_tab_card, doc_tab_list, doc_tab_trigger

_VIEW_TAB_VALUE = "view"
_CODE_TAB_VALUE = "code"
_DATA_TAB_VALUE = "data"


def _reflex_build_icon() -> rx.Component:
    """Create the Reflex Build mark for the demo action.

    Returns:
        The Reflex Build SVG icon.
    """
    return rx.el.svg(
        rx.el.rect(
            x="1",
            y="1",
            width="14",
            height="14",
            rx="3.5",
            fill="currentColor",
        ),
        rx.el.path(
            d="M9.75 9.16675V11.9376C9.75 12.0181 9.81529 12.0834 9.89583 12.0834H11.3542C11.4347 12.0834 11.5 12.0181 11.5 11.9376V9.31258C11.5 9.23204 11.4347 9.16675 11.3542 9.16675H9.75Z",
            fill="white",
        ),
        rx.el.path(
            d="M4.64583 3.91675C4.56529 3.91675 4.5 3.98204 4.5 4.06258V11.9376C4.5 12.0181 4.56529 12.0834 4.64583 12.0834H6.10417C6.18471 12.0834 6.25 12.0181 6.25 11.9376V9.31258C6.25 9.23204 6.31529 9.16675 6.39583 9.16675H9.75V7.41675H6.39583C6.31529 7.41675 6.25 7.35146 6.25 7.27091V5.81258C6.25 5.73204 6.31529 5.66675 6.39583 5.66675H9.60417C9.68471 5.66675 9.75 5.73204 9.75 5.81258V7.41675H11.3542C11.4347 7.41675 11.5 7.35146 11.5 7.27091V4.06258C11.5 3.98204 11.4347 3.91675 11.3542 3.91675H4.64583Z",
            fill="white",
        ),
        width="16",
        height="16",
        view_box="0 0 16 16",
        fill="none",
        class_name="text-primary-9",
        custom_attrs={"aria-hidden": "true"},
    )


def _reflex_build_action() -> rx.Component:
    """Create the external Reflex Build action for a demo.

    Returns:
        A ghost-highlight link styled as a button.
    """
    return rx.el.a(
        _reflex_build_icon(),
        rx.el.span("Start Building Now!"),
        ui.icon("ArrowUpRight01Icon", aria_hidden="true"),
        href=REFLEX_BUILD_URL,
        target="_blank",
        rel="noopener noreferrer",
        class_name=(
            f"{ui.button.class_names.for_button('ghost-highlight', 'sm')} "
            "mb-1.5 no-underline pl-0"
        ),
    )


def _doc_demo_header(*triggers: rx.Component) -> rx.Component:
    """Create the action and tab controls above a documentation demo.

    Args:
        triggers: Tab triggers associated with the demo.

    Returns:
        The demo header with the build action on the left.
    """
    return rx.el.div(
        _reflex_build_action(),
        doc_tab_list(*triggers),
        class_name=(
            "flex w-full flex-wrap items-end justify-between gap-x-2 gap-y-1 "
            "sm:flex-nowrap"
        ),
    )


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
        value=_VIEW_TAB_VALUE,
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

    return rx.box(
        rx.tabs.root(
            _doc_demo_header(
                doc_tab_trigger("View", value=_VIEW_TAB_VALUE, icon="eye"),
                doc_tab_trigger("Code", value=_CODE_TAB_VALUE, icon="code-xml"),
            ),
            doc_tab_card(
                _doc_view_panel(comp, demobox_props),
                _doc_code_panel(code, _CODE_TAB_VALUE, theme or "light"),
            ),
            default_value=_VIEW_TAB_VALUE,
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
            doc_tab_trigger("View", value=_VIEW_TAB_VALUE, icon="eye"),
            _doc_view_panel(comp),
        ),
        (
            doc_tab_trigger("Code", value=_CODE_TAB_VALUE, icon="code-xml"),
            _doc_code_panel(code, _CODE_TAB_VALUE),
        ),
    ]
    if data:
        tabs.append((
            doc_tab_trigger("Data", value=_DATA_TAB_VALUE, icon="database"),
            _doc_code_panel(data, _DATA_TAB_VALUE),
        ))

    return rx.box(
        rx.tabs.root(
            _doc_demo_header(*(trigger for trigger, _ in tabs)),
            doc_tab_card(*(panel for _, panel in tabs)),
            default_value=_VIEW_TAB_VALUE,
            class_name="w-full",
        ),
        class_name="w-full py-4 flex flex-col",
    )
