"""A quiet closing invitation using the editorial theme."""

import reflex as rx
from reflex_site_shared.components.marketing_button import button
from reflex_site_shared.constants import REFLEX_BUILD_URL

from reflex_docs.pages.docs_landing.views.layout import CONTAINER, FOCUS


def docs_cta() -> rx.Component:
    """Render an open closing invitation with the existing product and demo links.

    Returns:
        The closing call-to-action section of the documentation overview.
    """
    return rx.el.section(
        rx.el.div(
            rx.el.div(
                rx.el.h2(
                    "The platform to build and scale enterprise apps.",
                    id="docs-cta-title",
                    class_name="max-w-3xl font-heading text-3xl font-light leading-[1.08] tracking-[-0.04em] text-foreground text-balance sm:text-4xl lg:text-5xl",
                ),
                rx.el.p(
                    "Describe your idea, and let AI transform it into a complete, "
                    "production-ready Python web application.",
                    class_name="max-w-xl text-base font-normal leading-7 text-muted-foreground",
                ),
                rx.el.div(
                    rx.el.elements.a(
                        button(
                            "Try for free",
                            variant="primary",
                            size="lg",
                            class_name="!px-6 !font-normal",
                            native_button=False,
                        ),
                        href=REFLEX_BUILD_URL,
                        target="_blank",
                        rel="noopener noreferrer",
                        class_name=f"rounded-full {FOCUS}",
                    ),
                    rx.el.elements.a(
                        button(
                            "Book a Demo",
                            variant="ghost",
                            size="lg",
                            class_name="!border-0 !bg-muted !px-6 !font-normal !text-foreground !shadow-none hover:!bg-accent-hover",
                            native_button=False,
                        ),
                        href="https://reflex.dev/demo/",
                        class_name=f"rounded-full {FOCUS}",
                    ),
                    class_name="mt-2 flex flex-wrap items-center justify-center gap-x-7 gap-y-3",
                ),
                class_name="flex flex-col items-center gap-6 text-center",
            ),
            class_name="border-t border-border-subtle pt-12 sm:pt-16",
        ),
        aria_labelledby="docs-cta-title",
        class_name=f"docs-cta {CONTAINER} pb-16 sm:pb-20",
    )
