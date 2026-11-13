"""The about page: static content styled with Tailwind classes, and the custom 404 page."""

import reflex as rx

from playground.layout import layout

FEATURES = (
    ("State", "Substates with scalars, lists, dicts, dataclasses and models."),
    ("Events", "Sync, async, generator and background handlers, and chains."),
    ("Data", "A sqlite table seeded at start, with filters, sorting and forms."),
    ("Components", "Charts, grids, markdown, media and custom React code."),
    ("Collaboration", "Rooms whose sessions share one state and see each other."),
    ("Storage", "Cookies, localStorage and sessionStorage synced with the state."),
)


def feature_card(title: str, text: str) -> rx.Component:
    """Render one feature of the playground.

    Args:
        title: The feature.
        text: What it shows.

    Returns:
        A card styled with Tailwind classes.
    """
    return rx.el.div(
        rx.el.h3(title, class_name="text-lg font-semibold"),
        rx.el.p(text, class_name="text-sm opacity-80"),
        class_name="rounded-xl border p-4 shadow-sm",
    )


def about() -> rx.Component:
    """Render the about page.

    Returns:
        An introduction and a grid of feature cards.
    """
    return layout(
        rx.el.section(
            rx.el.h1("About the playground", class_name="text-3xl font-bold mb-2"),
            rx.el.p(
                "A Reflex app covering the framework's surface, and the fixture of the "
                "Reflex macro benchmarks.",
                class_name="mb-6 max-w-prose",
            ),
            rx.el.div(
                *[feature_card(title, text) for title, text in FEATURES],
                class_name="grid grid-cols-1 gap-4 md:grid-cols-3",
                id="about-features",
            ),
            class_name="w-full",
        )
    )


def not_found() -> rx.Component:
    """Render the custom 404 page.

    Returns:
        A message and a link home.
    """
    return layout(
        rx.vstack(
            rx.heading("Page not found", id="not-found"),
            rx.text("No playground page lives at this address."),
            rx.link("Back home", href="/", id="not-found-home"),
        )
    )
