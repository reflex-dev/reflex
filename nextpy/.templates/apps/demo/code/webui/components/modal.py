import nextpy as xt

from ...webui.state import State


def modal() -> xt.Component:
    """A modal to create a new chat.

    Returns:
        The modal component.
    """
    return xt.modal(
        xt.modal_overlay(
            xt.modal_content(
                xt.modal_header(
                    xt.hstack(
                        xt.text("Create new chat"),
                        xt.icon(
                            tag="close",
                            font_size="sm",
                            on_click=State.toggle_modal,
                            color="#fff8",
                            _hover={"color": "#fff"},
                            cursor="pointer",
                        ),
                        align_items="center",
                        justify_content="space-between",
                    )
                ),
                xt.modal_body(
                    xt.input(
                        placeholder="Type something...",
                        on_blur=State.set_new_chat_name,
                        bg="#222",
                        border_color="#fff3",
                        _placeholder={"color": "#fffa"},
                    ),
                ),
                xt.modal_footer(
                    xt.button(
                        "Create",
                        bg="#5535d4",
                        box_shadow="md",
                        px="4",
                        py="2",
                        h="auto",
                        _hover={"bg": "#4c2db3"},
                        on_click=State.create_chat,
                    ),
                ),
                bg="#222",
                color="#fff",
            ),
        ),
        is_open=State.modal_open,
    )
