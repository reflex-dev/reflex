"""Missing-page view using the same shell as the documentation landing page."""

import reflex as rx
from reflex_site_shared.components.marketing_button import button
from reflex_site_shared.route import Route


def not_found() -> rx.Component:
    """Render a recovery path inside the current documentation design.

    Returns:
        Docs navigation, missing-page message, and shared landing footer.
    """
    # These views depend on the page registry, so load them after registration.
    from reflex_docs.views.docs_navbar import docs_navbar
    from reflex_docs.views.editorial_footer import editorial_footer

    return rx.el.div(
        docs_navbar(),
        rx.el.main(
            rx.el.div(
                rx.el.p("404", class_name="text-sm font-book text-muted-foreground"),
                rx.el.h1(
                    "Page not found",
                    class_name="text-4xl sm:text-5xl font-book tracking-tight text-foreground",
                ),
                rx.el.p(
                    "We couldn't find that documentation page. Browse the docs or use search to find what you need.",
                    class_name="max-w-md text-base leading-7 text-muted-foreground",
                ),
                rx.el.elements.a(
                    button(
                        "Back to docs",
                        variant="primary",
                        size="md",
                        native_button=False,
                    ),
                    href="/docs/",
                    class_name="rounded-full focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ring",
                ),
                class_name="flex min-h-[65vh] flex-col items-start justify-center gap-6 mx-auto max-w-(--landing-layout-max-width) px-6 pb-16 pt-[calc(var(--docs-header-height)+4rem)]",
            ),
            editorial_footer(),
        ),
        class_name="min-h-screen bg-background",
    )


page404 = Route(
    path="/404",
    title="Page Not Found · Reflex Docs",
    component=not_found,
    meta=[{"name": "robots", "content": "noindex"}],
    add_as_page=False,
)
