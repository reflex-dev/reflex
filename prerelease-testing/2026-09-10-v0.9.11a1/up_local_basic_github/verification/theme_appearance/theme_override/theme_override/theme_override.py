"""Minimal repro: does a NESTED rx.theme(appearance=...) override light/dark?

Root app theme is pinned appearance="light" so the page is deterministically light.
Three nested boxes:
  A) stock rx.theme(appearance="dark")        -> claim: no dark class
  B) stock rx.theme(color_mode="dark")        -> claim: no dark class
  C) PatchedTheme(appearance="dark")          -> identical component whose _render
     re-adds the appearance prop the stock one strips; control that shows whether
     the bundled @radix-ui/themes honours the prop at all.
  D) rx.theme(accent_color="red")             -> control: a non-appearance prop DOES render
"""

from typing import Any

import reflex as rx
from reflex.components.tags import Tag
from reflex_components_radix.themes.base import Theme


class PatchedTheme(Theme):
    """rx.theme with the appearance prop NOT stripped."""

    def _render(self, props: dict[str, Any] | None = None) -> Tag:
        tag = super()._render(props)
        if self.appearance is not None:
            # Tag.add_props returns a NEW tag (dataclasses.replace) - must reassign.
            tag = tag.add_props(appearance=self.appearance)
        return tag


patched_theme = PatchedTheme.create


class ThemeState(rx.State):
    """Query-param driven appearance, like reflex-examples/github-stats/widget."""

    @rx.var
    def appearance_param(self) -> str:
        return self.router.url.query_parameters.get("appearance", "inherit")


def swatch(label: str) -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.heading(label, size="3"),
            rx.text("body text", size="2"),
            rx.button("button"),
        ),
        id=f"card-{label}",
    )


def index() -> rx.Component:
    return rx.vstack(
        rx.heading("nested rx.theme appearance override"),
        rx.text("root app theme appearance='light'"),
        rx.box(rx.theme(swatch("A-stock-appearance"), appearance="dark"), id="wrap-a"),
        rx.box(rx.theme(swatch("B-stock-color_mode"), color_mode="dark"), id="wrap-b"),
        rx.box(patched_theme(swatch("C-patched-appearance"), appearance="dark"), id="wrap-c"),
        rx.box(rx.theme(swatch("D-accent-control"), accent_color="red"), id="wrap-d"),
        rx.box(
            rx.theme(swatch("E-state-var"), appearance=ThemeState.appearance_param),
            id="wrap-e",
        ),
        spacing="4",
        padding="1em",
    )


app = rx.App(theme=rx.theme(appearance="light"))
app.add_page(index, route="/")
