"""Components for rendering code demos in the documentation."""

import textwrap
from typing import Any

import ruff_format

import reflex as rx

from .code import code_block, code_block_dark


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
        class_name="flex flex-col p-6 rounded-xl overflow-x-auto border border-slate-4 bg-slate-2 items-center justify-center w-full",
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

    if demobox_props.pop("toggle", False):
        return rx.tabs.root(
            rx.tabs.list(
                rx.tabs.trigger(
                    rx.box(
                        "UI",
                    ),
                    value="tab1",
                    class_name="tab-style",
                ),
                rx.tabs.trigger(
                    rx.box(
                        "Code",
                    ),
                    value="tab2",
                    class_name="tab-style",
                ),
                class_name="justify-end",
            ),
            rx.tabs.content(
                rx.box(docdemobox(comp, **(demobox_props or {})), class_name="my-4"),
                value="tab1",
            ),
            rx.tabs.content(
                rx.box(doccode(code, theme=theme or "light"), class_name="my-4"),
                value="tab2",
            ),
            default_value="tab1",
        )
    # Create the demo.
    return rx.box(
        docdemobox(comp, **(demobox_props or {})),
        doccode(code, theme=theme or "light"),
        class_name="py-4 gap-4 flex flex-col w-full",
        **props,
    )


def docgraphing(
    code: str,
    comp: rx.Component | None = None,
    data: str | None = None,
):
    """Docgraphing.

    Returns:
        The component.
    """
    return rx.box(
        rx.flex(
            comp,
            class_name="w-full flex flex-col p-6 rounded-xl overflow-x-auto border border-slate-4 bg-slate-2 items-center justify-center",
        ),
        rx.tabs.root(
            rx.tabs.list(
                rx.tabs.trigger("Code", value="code", class_name="tab-style"),
                rx.tabs.trigger("Data", value="data", class_name="tab-style"),
                justify_content="end",
            ),
            rx.box(
                rx.tabs.content(doccode(code), value="code", class_name="w-full px-0"),
                rx.tabs.content(
                    doccode(data or ""), value="data", class_name="w-full px-0"
                ),
                class_name="w-full my-4",
            ),
            default_value="code",
            class_name="w-full mt-6 justify-end",
        ),
        class_name="w-full py-4 flex flex-col",
    )
