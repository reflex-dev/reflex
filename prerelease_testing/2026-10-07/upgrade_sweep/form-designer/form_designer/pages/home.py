import importlib.metadata
from pathlib import Path

import reflex as rx

from .. import style, routes
from ..components import navbar


def home_page() -> rx.Component:
    readme_content = Path(__file__).resolve().parent.parent.parent / "README.md"
    return style.layout(
        navbar(),
        rx.link("Create or Edit Forms", href=routes.FORM_EDIT_NEW),
        rx.divider(),
        rx.card(
            rx.inset(
                rx.badge(rx.code("README.md"), width="100%", size="2"),
                side="top",
                pb="current",
                clip="padding-box",
            ),
            rx.markdown(readme_content.read_text()),
            margin_y="2em",
        ),
        rx.hstack(
            rx.logo(),
            rx.text(f"v{importlib.metadata.version('reflex')}", size="1"),
            align="center",
        ),
    )
