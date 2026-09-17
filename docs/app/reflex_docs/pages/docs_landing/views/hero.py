"""Editorial introduction to the documentation."""

import reflex as rx
import reflex_components_internal as ui
from reflex_site_shared.components.marketing_button import button
from reflex_site_shared.views.hosting_banner import HostingBannerState

from reflex_docs.pages.docs import getting_started
from reflex_docs.pages.docs_landing.views.artwork import artwork


def hero() -> rx.Component:
    """Render the docs introduction using the marketing typography and actions."""
    return rx.el.section(
        rx.el.div(
            rx.el.h1(
                "Reflex Documentation",
                class_name="text-foreground text-4xl sm:text-5xl lg:text-6xl font-book tracking-[-0.03em] leading-[1.06] text-balance",
            ),
            rx.el.p(
                "Get up and running with Reflex in minutes. A complete set of resources "
                "to build, deploy, and scale your application.",
                class_name="max-w-2xl text-muted-foreground text-base sm:text-lg leading-7 font-normal text-balance",
            ),
            rx.el.div(
                rx.el.a(
                    button(
                        "Build with AI",
                        ui.icon("ArrowRight01Icon"),
                        variant="primary",
                        size="lg",
                        class_name="!px-6",
                        native_button=False,
                    ),
                    href="/ai/",
                    class_name="rounded-full focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ring",
                ),
                rx.el.a(
                    button(
                        "Explore Framework",
                        ui.icon("ArrowRight01Icon"),
                        variant="outline",
                        size="lg",
                        class_name="!px-6",
                        native_button=False,
                    ),
                    href=getting_started.introduction.path,
                    class_name="rounded-full focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ring",
                ),
                class_name="flex flex-wrap items-center gap-3",
            ),
            class_name="relative z-10 flex flex-col items-start gap-6 lg:max-w-[55%]",
        ),
        artwork(
            "squares_docs_logo",
            class_name="docs-hero-art absolute left-1/2 w-1/2 max-lg:hidden",
        ),
        style={
            "--docs-hero-header-height": rx.cond(
                HostingBannerState.is_banner_visible, "6.5rem", "4rem"
            )
        },
        class_name="docs-hero relative max-w-[90rem] px-4 min-[55rem]:px-8 lg:px-12 mx-auto w-full pb-16 lg:pb-24",
    )
