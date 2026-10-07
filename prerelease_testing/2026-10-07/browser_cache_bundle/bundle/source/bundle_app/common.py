"""Shared shell without optional heavy component imports."""

import importlib.metadata as md
import os
from pathlib import Path
import reflex as rx

assert str(Path(os.environ["REFLEX_EXPECT_ENV"]) / "lib") in rx.__file__, rx.__file__
VERSION = md.version("reflex")


def shell(title: str, *children: rx.Component) -> rx.Component:
    """Wrap each route with a common navigation and stable content container.

    Args:
        title: Visible page title.
        children: Page content.

    Returns:
        Shared route layout.
    """
    return rx.vstack(
        rx.hstack(
            rx.text("Operations workspace", weight="bold"),
            *[
                rx.link(label, href=path, id=f"nav-{label.lower()}")
                for label, path in [
                    ("Home", "/"),
                    ("Dashboard", "/dashboard"),
                    ("Reports", "/reports"),
                    ("Editor", "/editor"),
                ]
            ],
            spacing="4",
        ),
        rx.heading(title, id="page-title"),
        *children,
        rx.text(f"reflex {VERSION}", id="version", size="1"),
        width="100%",
        max_width="1100px",
        padding="24px",
        spacing="4",
    )
