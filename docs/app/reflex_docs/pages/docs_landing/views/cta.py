"""A quiet closing invitation using the editorial theme."""

import reflex as rx
import reflex_components_internal as ui
from reflex_components_internal.blocks.demo_form import demo_form_open_cs
from reflex_site_shared.components.marketing_button import button
from reflex_site_shared.constants import REFLEX_BUILD_URL

from reflex_docs.pages.docs_landing.views.artwork import artwork


def docs_cta() -> rx.Component:
    """Render the closing actions alongside the original product illustration."""
    return rx.el.section(
        rx.el.div(
            rx.el.div(
                rx.el.h2(
                    "The platform to build and scale enterprise apps.",
                    id="docs-cta-title",
                    class_name="max-w-xl text-3xl sm:text-4xl font-book leading-[1.15] tracking-[-0.03em] text-foreground text-balance",
                ),
                rx.el.p(
                    "Describe your idea, and let AI transform it into a complete, "
                    "production-ready Python web application.",
                    class_name="max-w-lg text-base leading-7 font-normal text-muted-foreground",
                ),
                rx.el.div(
                    rx.el.elements.a(
                        button(
                            "Try for free",
                            ui.icon("ArrowRight01Icon", aria_hidden=True),
                            variant="primary",
                            native_button=False,
                        ),
                        href=REFLEX_BUILD_URL,
                        target="_blank",
                        rel="noopener noreferrer",
                        class_name="rounded-full focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ring",
                    ),
                    button(
                        "Book a Demo",
                        variant="ghost",
                        aria_haspopup="dialog",
                        on_click=rx.call_function(demo_form_open_cs.set_value(True)),
                    ),
                    class_name="flex flex-wrap items-center gap-x-5 gap-y-3",
                ),
                class_name="relative z-10 flex flex-col items-start gap-6 p-6 sm:p-10 lg:py-14 lg:pl-12 lg:pr-0",
            ),
            artwork(
                "cta_illustration",
                "docs-cta-art self-center w-full max-lg:hidden",
            ),
            class_name="grid lg:grid-cols-[1.1fr_1fr] items-center overflow-hidden rounded-panel border border-border-subtle bg-muted",
        ),
        aria_labelledby="docs-cta-title",
        class_name="docs-cta mx-auto w-full max-w-(--landing-layout-max-width) px-6 xl:px-0 py-16 lg:py-24",
    )
