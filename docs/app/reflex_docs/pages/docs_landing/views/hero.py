"""Editorial introduction to the documentation."""

import reflex as rx
import reflex_components_internal as ui
from reflex_site_shared.components.marketing_button import button

from reflex_docs.pages.docs import getting_started


def hero() -> rx.Component:
    """Render the docs introduction using the marketing typography and actions."""
    return rx.el.section(
        rx.el.h1(
            "Reflex Documentation",
            class_name="text-foreground text-4xl sm:text-5xl lg:text-6xl font-book tracking-[-0.03em] leading-[1.06] text-balance",
        ),
        rx.el.p(
            "Get up and running with Reflex in minutes. A complete set of resources "
            "to build, deploy, and scale your application.",
            class_name="max-w-2xl text-muted-foreground text-base sm:text-lg leading-7 font-normal text-balance",
        ),
        rx.el.a(
            button(
                "Get Started",
                ui.icon("ArrowRight01Icon"),
                variant="primary",
                size="lg",
                native_button=False,
            ),
            to=getting_started.introduction.path,
            class_name="rounded-full focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ring",
        ),
        class_name="docs-hero flex flex-col items-start gap-6 max-w-(--landing-layout-max-width) mx-auto w-full px-6 xl:px-0 pb-16 lg:pb-24",
    )
