from typing import Callable

import reflex as rx

from chat_v2.components.buttons import button_with_icon

from .pop_up import LibraryPrompt


def input_box(
    input_box_id: str,
    input_box_text_value: str,
    input_prompt_is_loading: bool,
    input_prompt_on_change: Callable,
    send_button_on_click: Callable,
    library_prompt: LibraryPrompt,
    **kwargs,
):
    return rx.form(
        rx.vstack(
            rx.hstack(
                rx.tooltip(
                    rx.box(
                        rx.icon(
                            "info",
                            size=18,
                        ),
                        padding_top="6px",
                    ),
                    content="Enter a question to get a response.",
                ),
                rx.text_area(
                    value=input_box_text_value,
                    placeholder="How can I help?",
                    on_change=input_prompt_on_change,
                    width="100%",
                    background_color=rx.color(
                        color="indigo",
                        shade=2,
                    ),
                    variant="soft",
                    outline="none",
                    line_height="150%",
                    color=rx.color(
                        color="slate",
                        shade=11,
                    ),
                    enter_key_submit=True,
                    auto_height=True,
                    min_height="0px",
                    rows="1",
                    **kwargs,
                ),
                width="100%",
                align="start",
            ),
            rx.divider(),
            rx.hstack(
                rx.hstack(
                    rx.button(
                        rx.icon(
                            tag="book",
                            size=18,
                        ),
                        "Library",
                        radius="large",
                        cursor="pointer",
                        padding="18px 16px",
                        bg="transparent",
                        border=rx.color_mode_cond(
                            light="1px solid indigo",
                            dark="1px solid slate",
                        ),
                        color=rx.color(
                            color="slate",
                            shade=11,
                        ),
                        on_click=library_prompt.toggle_prompt_library,
                        id=input_box_id,
                        type="button",
                    ),
                    rx.spacer(),
                    *[
                        rx.icon(
                            tag=name,
                            size=18,
                            color=rx.color(
                                color="slate",
                                shade=11,
                            ),
                        )
                        for name in ["paperclip", "image", "mic", "layout-grid"]
                    ],
                    display="flex",
                    align="center",
                ),
                button_with_icon(
                    text="Send Message",
                    icon="send",
                    is_loading=input_prompt_is_loading,
                ),
                width="100%",
                display="flex",
                justify="between",
            ),
            width="100%",
            display="flex",
            align="start",
            padding="24px",
            gap="16px 24px",
            border_radius="16px",
            border=rx.color_mode_cond(
                f"2px solid {rx.color('indigo', 3)}",
                f"1px solid {rx.color('slate', 7, True)}",
            ),
            background_color=rx.color(
                color="indigo",
                shade=2,
            ),
            box_shadow=rx.color_mode_cond(
                light="0px 1px 3px rgba(25, 33, 61, 0.1)",
                dark="none",
            ),
        ),
        on_submit=send_button_on_click,
    )
