"""Minimal repro: a computed rx.Component var (dynamic component) containing rx.icon.

Three variants, all selected by environment variable (nothing else changes):

* default                 nothing bundled by the app
* ``REPRO_BUNDLE=1``      ``bundle_library("lucide-react")`` at module import
* ``REPRO_PLUGIN=1``      lucide-react declared by a compiler plugin's
                          ``get_frontend_dependencies()`` (the supported route;
                          ``rxconfig.py`` reads the same variable)

Pages:
  /dyn  static rx.icon + a dynamic block holding rx.icon (subpath import) and text
  /ctl  control dynamic block built only from rx.el elements (no third-party import)
  /mix  the control block plus exactly one rx.icon
"""

import os

import reflex as rx
from reflex.components.dynamic import bundle_library

BUNDLE = os.environ.get("REPRO_BUNDLE") == "1"
if BUNDLE:
    bundle_library("lucide-react")


class DynState(rx.State):
    """State exposing dynamic components as computed vars."""

    label: str = "start"

    @rx.var
    def icon_block(self) -> rx.Component:
        """Dynamic component that contains a lucide icon (deep subpath import).

        Returns:
            The dynamic component.
        """
        return rx.vstack(
            rx.icon("apple", id="dyn-icon"),
            rx.text(f"icon-label: {self.label}", id="dyn-label"),
        )

    @rx.var
    def plain_block(self) -> rx.Component:
        """Control: dynamic component built only from plain HTML elements.

        No third-party import at all, so it needs no CDN and no window lib.

        Returns:
            The dynamic component.
        """
        return rx.el.div(
            rx.el.p("plain-box", id="ctl-box"),
            rx.el.p(f"ctl-label: {self.label}", id="ctl-label"),
        )

    @rx.var
    def el_icon_block(self) -> rx.Component:
        """Same plain-element block, with one rx.icon added.

        Returns:
            The dynamic component.
        """
        return rx.el.div(
            rx.icon("apple", id="mix-icon"),
            rx.el.p("mix-box", id="mix-box"),
            rx.el.p(f"mix-label: {self.label}", id="mix-label"),
        )

    @rx.event
    def relabel(self):
        """Change the label rendered inside both dynamic components."""
        self.label = "clicked"


def shell(*kids: rx.Component) -> rx.Component:
    """Shared layout.

    Args:
        kids: Page content.

    Returns:
        The layout component.
    """
    return rx.vstack(
        rx.hstack(
            rx.link("dyn", href="/dyn", id="lnk-dyn"),
            rx.link("ctl", href="/ctl", id="lnk-ctl"),
            rx.link("mix", href="/mix", id="lnk-mix"),
        ),
        rx.text(f"bundle_library called: {BUNDLE}", id="mode"),
        *kids,
        rx.button("relabel", on_click=DynState.relabel, id="btn-relabel"),
        padding="2em",
        align="start",
    )


@rx.page(route="/", title="home")
def index() -> rx.Component:
    """Home page.

    Returns:
        The page component.
    """
    return shell(rx.heading("HOME", id="hd"))


@rx.page(route="/dyn", title="dyn")
def dyn() -> rx.Component:
    """Dynamic component containing an icon.

    Returns:
        The page component.
    """
    return shell(
        rx.heading("DYN", id="hd"),
        rx.icon("banana", id="static-icon"),
        DynState.icon_block,
    )


@rx.page(route="/ctl", title="ctl")
def ctl() -> rx.Component:
    """Control: dynamic component with no subpath import.

    Returns:
        The page component.
    """
    return shell(
        rx.heading("CTL", id="hd"),
        DynState.plain_block,
    )


@rx.page(route="/mix", title="mix")
def mix() -> rx.Component:
    """Plain-element dynamic block plus one icon.

    Returns:
        The page component.
    """
    return shell(
        rx.heading("MIX", id="hd"),
        DynState.el_icon_block,
    )


app = rx.App()
