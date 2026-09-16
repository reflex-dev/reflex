"""Docs-specific primary navigation for compact screens."""

import reflex as rx
import reflex_components_internal as ui
from reflex_site_shared.views.sidebar import docs_sidebar_drawer


def navbar_sidebar_button() -> rx.Component:
    """Render a native disclosure with the same destinations as desktop docs.

    Returns:
        A keyboard-accessible docs navigation menu.
    """
    return rx.el.details(
        rx.el.summary(
            ui.icon("Menu01Icon", class_name="size-5 group-open/docs-menu:hidden"),
            ui.icon(
                "Cancel01Icon", class_name="hidden size-5 group-open/docs-menu:block"
            ),
            aria_label="Toggle navigation menu",
            class_name="flex size-9 cursor-pointer list-none items-center justify-center rounded-full text-foreground hover:bg-accent focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring [&::-webkit-details-marker]:hidden",
        ),
        rx.el.div(
            *[
                rx.el.elements.a(
                    label,
                    ui.icon(
                        "ArrowUpRight01Icon",
                        aria_hidden=True,
                        class_name="size-4 shrink-0",
                    ),
                    href=href,
                    class_name="flex w-full items-center justify-between gap-3 border-b border-border px-4 py-4 text-base font-medium text-foreground transition-colors hover:bg-accent focus-visible:outline-2 focus-visible:outline-ring last:border-b-0",
                )
                for label, href in (
                    ("Overview", "/docs/"),
                    ("Build with AI", "/docs/ai/"),
                    ("Framework", "/docs/getting-started/introduction/"),
                    ("Cloud", "/docs/hosting/deploy-quick-start/"),
                    ("XY", "/docs/xy/"),
                    ("Book a Demo", "https://reflex.dev/demo/"),
                )
            ],
            aria_label="Documentation navigation",
            role="navigation",
            class_name="fixed inset-x-0 top-[var(--docs-header-height)] max-h-[calc(100dvh-var(--docs-header-height))] overflow-y-auto border-b border-border-subtle bg-background px-6 py-4 shadow-small",
        ),
        class_name="group/docs-menu",
    )


__all__ = ["docs_sidebar_drawer", "navbar_sidebar_button"]
