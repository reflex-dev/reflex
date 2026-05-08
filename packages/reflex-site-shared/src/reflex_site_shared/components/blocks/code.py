"""Code block components for documentation pages."""

from reflex_components_code.shiki_code_block import code_block as shiki_code_block

import reflex as rx
import reflex_site_shared.styles.fonts as fonts
from reflex_site_shared import styles

EXPAND_THRESHOLD_LINES = 20
COLLAPSED_MAX_HEIGHT = "400px"


@rx.memo
def _plain_code_block(code: str, language: str):
    """Shared plain code block implementation.

    Returns:
        The component.
    """
    return rx.box(
        shiki_code_block(
            code,
            language=language,
            class_name="code-block",
            can_copy=True,
        ),
        class_name="relative mb-4",
    )


def code_block(code: str, language: str):
    """Code block. Shows an Expand/Collapse toggle when longer than the threshold.

    Returns:
        The component.
    """
    # During import-graph introspection ``code`` may be a Var, not a Python str.
    # Skip the line-count check in that case and render the plain block.
    if not isinstance(code, str):
        return _plain_code_block(code=code, language=language)
    if code.count("\n") + 1 > EXPAND_THRESHOLD_LINES:
        return rx.el.div(
            _plain_code_block(code=code, language=language),
            rx.el.details(
                rx.el.summary(
                    rx.el.span(
                        "Expand",
                        rx.icon(
                            "chevron-down",
                            size=14,
                            class_name="inline-block align-[-2px] ml-1",
                        ),
                        class_name="group-open/details:hidden",
                    ),
                    rx.el.span(
                        "Collapse",
                        rx.icon(
                            "chevron-up",
                            size=14,
                            class_name="inline-block align-[-2px] ml-1",
                        ),
                        class_name="hidden group-open/details:inline",
                    ),
                    class_name=(
                        "list-none cursor-pointer text-center text-sm font-medium "
                        "text-[var(--c-slate-11)] hover:text-[var(--c-slate-12)] "
                        "pt-12 pb-3 rounded-b-xl "
                        "bg-gradient-to-t from-[var(--c-slate-2)] from-55% to-transparent "
                        "group-open/details:pt-3 group-open/details:bg-none "
                        "[&::-webkit-details-marker]:hidden [&::marker]:hidden"
                    ),
                ),
                class_name="group/details absolute bottom-0 left-0 right-0",
            ),
            class_name=(
                "relative max-h-[400px] overflow-hidden mt-4 mb-4 rounded-xl "
                "border border-[var(--c-slate-4)] bg-[var(--c-slate-2)] "
                "[&_.code-block]:!border-0 "
                "has-[details[open]]:max-h-none"
            ),
        )
    return _plain_code_block(code=code, language=language)


@rx.memo
def code_block_dark(code: str, language: str):
    """Code block dark.

    Returns:
        The component.
    """
    return rx.box(
        shiki_code_block(
            code,
            language=language,
            class_name="code-block",
            can_copy=True,
        ),
        class_name="relative mb-4",
    )


def code_block_markdown(*children, **props):
    """Code block markdown.

    Returns:
        The component.
    """
    language = props.get("language", "plain")
    return code_block(code=children[0], language=language)


def code_block_markdown_dark(*children, **props):
    """Code block markdown dark.

    Returns:
        The component.
    """
    language = props.get("language", "plain")
    return code_block_dark(code=children[0], language=language)


def doccmdoutput(
    command: str,
    output: str,
) -> rx.Component:
    """Create a documentation code snippet.

    Args:
        command: The command to display.
        output: The output of the command.

    Returns:
        The styled command and its example output.
    """
    return rx.vstack(
        shiki_code_block(
            command,
            can_copy=True,
            border_radius=styles.DOC_BORDER_RADIUS,
            background="transparent",
            theme="ayu-dark",
            language="bash",
            code_tag_props={
                "style": {
                    "fontFamily": "inherit",
                }
            },
            style=fonts.code,
            font_family="JetBrains Mono",
            width="100%",
        ),
        shiki_code_block(
            output,
            can_copy=False,
            border_radius="12px",
            background="transparent",
            theme="ayu-dark",
            language="log",
            code_tag_props={
                "style": {
                    "fontFamily": "inherit",
                }
            },
            style=fonts.code,
            font_family="JetBrains Mono",
            width="100%",
        ),
        padding_y="1em",
    )
