"""The main Chat app."""

import reflex as rx

from ..webui import styles
from ..webui.components import chat, modal, navbar, sidebar
from ..webui.state import State
from ..styles import *


def chatapp_page() -> rx.Component:
    """The main app."""
    return rx.box(
        rx.vstack(
            navbar(),
            chat.chat(),
            chat.action_bar(),
            sidebar(),
            modal(),
            bg=styles.bg_dark_color,
            color=styles.text_light_color,
            min_h="100vh",
            align_items="stretch",
            spacing="0",
            style=template_content_style,
        ),
        style=template_page_style,
    )
