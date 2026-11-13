"""A neutral error page matching the marketing site."""

import reflex as rx
from reflex_site_shared.components.marketing_button import button
from reflex_site_shared.route import Route
from reflex_site_shared.views.marketing_footer import marketing_footer
from reflex_site_shared.views.marketing_navbar import marketing_navbar


def _page404() -> rx.Component:
    """Render the marketing error layout with a local recovery link.

    Returns:
        The complete error page, including navigation and footer.
    """
    return rx.el.div(
        marketing_navbar(show_banner=False),
        rx.el.main(
            rx.el.section(
                rx.el.div(
                    rx.el.p(
                        "404", class_name="text-sm font-medium text-muted-foreground"
                    ),
                    rx.el.h1(
                        "Page not found.",
                        class_name="mt-5 text-page-title font-book text-foreground",
                    ),
                    rx.el.p(
                        "The link may have changed, or this page may no longer be available.",
                        class_name="mx-auto mt-6 max-w-[30rem] text-base leading-7 text-muted-foreground sm:text-lg",
                    ),
                    rx.el.div(
                        rx.el.a(
                            button(
                                "Back to home",
                                variant="primary",
                                size="md",
                                native_button=False,
                            ),
                            href="/",
                            class_name="rounded-control focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring",
                        ),
                        rx.el.elements.a(
                            button(
                                "Explore the platform",
                                rx.icon("arrow-right", size=16, aria_hidden=True),
                                variant="ghost",
                                size="md",
                                native_button=False,
                            ),
                            href="https://reflex.dev/platform/",
                            class_name="rounded-control focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring",
                        ),
                        class_name="mt-9 flex flex-wrap items-center justify-center gap-x-7 gap-y-3",
                    ),
                    class_name="flex min-h-[30rem] flex-col items-center justify-center rounded-panel border border-border-subtle bg-muted px-6 py-24 text-center sm:min-h-[34rem]",
                ),
                class_name="mx-auto w-full max-w-[90rem] px-6 py-12 sm:px-10 sm:py-16",
                aria_label="Page not found",
            ),
            class_name="w-full pt-16",
        ),
        marketing_footer(show_color_mode_toggle=True),
        class_name="min-h-screen bg-background text-foreground font-instrument-sans",
    )


page404 = Route(
    path="/404",
    title="Page not found · Reflex",
    description="This page could not be found. Explore Reflex or return to the homepage.",
    meta=[{"name": "robots", "content": "noindex, follow"}],
    add_as_page=False,
    component=_page404,
)
