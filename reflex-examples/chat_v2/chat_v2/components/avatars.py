import reflex as rx


def chat_message_avatar(
    src: str,
):
    return rx.avatar(
        src=src,
        size="2",
        border_radius="100%",
    )
