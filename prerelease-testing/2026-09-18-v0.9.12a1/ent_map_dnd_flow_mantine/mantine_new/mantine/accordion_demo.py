"""Accordion demo page."""

import reflex as rx

import reflex_enterprise as rxe

from .common import demo


@demo(
    route="/accordion",
    title="Accordion",
    description="An accordion is a component that displays a list of items in a collapsible format.",
)
def accordion_page():
    """Accordion demo page."""
    return rx.vstack(
        rxe.mantine.accordion(
            rxe.mantine.accordion.item(
                rxe.mantine.accordion.control("Customization"),
                rxe.mantine.accordion.panel(
                    rx.text(
                        "The Mantine Accordion component supports various customization options including different variants, chevron positions, and multiple selection modes."
                    )
                ),
                value="customization",
                width="100%",
            ),
            rxe.mantine.accordion.item(
                rxe.mantine.accordion.control("Accessibility"),
                rxe.mantine.accordion.panel(
                    rx.text(
                        "Accordions are keyboard accessible and follow WAI-ARIA guidelines. Users can navigate between items using arrow keys and toggle panels with Enter or Space."
                    )
                ),
                value="accessibility",
                width="100%",
            ),
            rxe.mantine.accordion.item(
                rxe.mantine.accordion.control(
                    rx.hstack(
                        rx.icon("info"),
                        rx.text("With Icon"),
                        spacing="2",
                    )
                ),
                rxe.mantine.accordion.panel(
                    rx.text(
                        "You can add icons or other components to the accordion control to enhance visual appearance."
                    )
                ),
                value="icon",
                width="100%",
            ),
            rxe.mantine.accordion.item(
                rxe.mantine.accordion.control("Disabled Item", disabled=True),
                rxe.mantine.accordion.panel(
                    rx.text("This item is disabled and cannot be opened.")
                ),
                value="disabled",
                width="100%",
            ),
            variant="contained",
            chevron_position="left",
            default_value="customization",
            multiple=True,
            width="30rem",
            on_change=rx.toast("Value changed"),
        ),
    )
