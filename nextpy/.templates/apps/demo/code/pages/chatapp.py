"""The main Chat app."""

import nextpy as xt

from ..styles import *
from ..webui import styles
from ..webui.components import chat, modal, navbar, sidebar


def chatapp_page() -> xt.Component:
    """The main app.

    Returns:
        The UI for the main app.
    """
    return xt.box(
        xt.vstack(
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
