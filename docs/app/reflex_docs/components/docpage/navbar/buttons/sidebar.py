"""Docs-specific primary navigation for compact screens."""

import reflex as rx
import reflex_components_internal as ui
from reflex_site_shared.views.sidebar import docs_sidebar_drawer

from reflex_docs import sections


def navbar_sidebar_button(active_tab: rx.Var[str] | str = "") -> rx.Component:
    """Render a native disclosure with the same destinations as desktop docs.

    Args:
        active_tab: The navbar tab of the current page (see ``reflex_docs.sections``),
            or an empty string when no section is current.

    Returns:
        A keyboard-accessible docs navigation menu.
    """
    # The pages package imports this module, so its routes load at call time.
    from reflex_docs.pages.docs import cloud, getting_started

    return rx.el.details(
        rx.el.summary(
            ui.icon("Menu01Icon", class_name="size-5 group-open/docs-menu:hidden"),
            ui.icon(
                "Cancel01Icon", class_name="hidden size-5 group-open/docs-menu:block"
            ),
            aria_label="Toggle navigation menu",
            class_name="docs-navbar-menu-trigger flex size-9 cursor-pointer list-none items-center justify-center rounded-[8px] text-foreground hover:bg-accent focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring [&::-webkit-details-marker]:hidden",
        ),
        rx.el.div(
            *[
                rx.el.elements.a(
                    label,
                    # Only a destination off the docs earns the external-link arrow.
                    *(
                        [
                            ui.icon(
                                "ArrowUpRight01Icon",
                                aria_hidden=True,
                                class_name="size-4 shrink-0",
                            )
                        ]
                        if tab is None
                        else []
                    ),
                    href=href,
                    aria_current=rx.cond(active_tab == tab, "page", None),
                    class_name=ui.cn(
                        "docs-navbar-mobile-link flex w-full items-center justify-between gap-3 border-b border-border px-4 py-4 text-base font-normal text-foreground transition-colors duration-150 hover:bg-accent focus-visible:outline-2 focus-visible:outline-ring motion-reduce:transition-none last:border-b-0",
                        rx.cond(active_tab == tab, "bg-accent", ""),
                    ),
                )
                for label, href, tab in (
                    ("Overview", "/docs/", sections.OVERVIEW),
                    ("Build with AI", "/docs/ai/", sections.AI),
                    (
                        "Framework",
                        f"/docs{getting_started.introduction.path}",
                        sections.FRAMEWORK,
                    ),
                    ("Cloud", f"/docs{cloud.overview.path}", sections.CLOUD),
                    ("XY", "/docs/xy/", sections.XY),
                    ("Book a Demo", "https://reflex.dev/demo/", None),
                )
            ],
            aria_label="Documentation navigation",
            role="navigation",
            class_name="docs-navbar-mobile-panel fixed inset-x-0 top-[var(--docs-header-height)] max-h-[calc(100dvh-var(--docs-header-height))] overflow-y-auto border-b border-border-subtle bg-background px-6 py-4 shadow-small",
        ),
        class_name="docs-navbar-menu group/docs-menu",
    )


__all__ = ["docs_sidebar_drawer", "navbar_sidebar_button"]
