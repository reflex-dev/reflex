import nextpy as xt

from ...webui import styles
from ...webui.components import loading_icon
from ...webui.state import QA, State


def message(qa: QA) -> xt.Component:
    """A single question/answer message.

    Args:
        qa: The question/answer pair.

    Returns:
        A component displaying the question/answer pair.
    """
    return xt.box(
        xt.box(
            xt.text(
                qa.question,
                bg=styles.border_color,
                shadow=styles.shadow_light,
                **styles.message_style,
            ),
            text_align="right",
            margin_top="1em",
        ),
        xt.box(
            xt.text(
                qa.answer,
                bg=styles.accent_color,
                shadow=styles.shadow_light,
                **styles.message_style,
            ),
            text_align="left",
            padding_top="1em",
        ),
        width="100%",
    )


def chat() -> xt.Component:
    """List all the messages in a single conversation.

    Returns:
        A component displaying all the messages in a single conversation.
    """
    return xt.vstack(
        xt.box(xt.foreach(State.chats[State.current_chat], message)),
        py="8",
        flex="1",
        width="100%",
        max_w="3xl",
        padding_x="4",
        align_self="center",
        overflow="hidden",
        padding_bottom="5em",
        **styles.base_style[xt.Vstack],
    )


def action_bar() -> xt.Component:
    """The action bar to send a new message.

    Returns:
        The action bar to send a new message.
    """
    return xt.box(
        xt.vstack(
            xt.form(
                xt.form_control(
                    xt.hstack(
                        xt.input(
                            placeholder="Type something...",
                            value=State.question,
                            on_change=State.set_question,
                            _placeholder={"color": "#fffa"},
                            _hover={"border_color": styles.accent_color},
                            style=styles.input_style,
                        ),
                        xt.button(
                            xt.cond(
                                State.processing,
                                loading_icon(height="1em"),
                                xt.text("Send"),
                            ),
                            type_="submit",
                            _hover={"bg": styles.accent_color},
                            style=styles.input_style,
                        ),
                        **styles.base_style[xt.Hstack],
                    ),
                    is_disabled=State.processing,
                ),
                on_submit=State.process_question,
                width="100%",
            ),
            xt.text(
                "NextpyGPT may return factually incorrect or misleading responses. Use discretion.",
                font_size="xs",
                color="#fff6",
                text_align="center",
            ),
            width="100%",
            max_w="3xl",
            mx="auto",
            **styles.base_style[xt.Vstack],
        ),
        position="sticky",
        bottom="0",
        left="0",
        py="4",
        backdrop_filter="auto",
        backdrop_blur="lg",
        border_top=f"1px solid {styles.border_color}",
        align_items="stretch",
        width="100%",
    )
