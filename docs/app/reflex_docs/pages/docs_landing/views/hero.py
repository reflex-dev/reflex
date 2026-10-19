"""Editorial introduction to the documentation."""

import reflex as rx
import reflex_components_internal as ui
from reflex_site_shared.components.marketing_button import button
from reflex_site_shared.views.hosting_banner import HostingBannerState

from reflex_docs.pages.docs import getting_started, hosting
from reflex_docs.pages.docs.library import library
from reflex_docs.pages.docs_landing.views.layout import CONTAINER, FOCUS


def _guide(title: str, description: str, href: str) -> rx.Component:
    """Render a compact navigation row in the hero's guide index.

    Args:
        title: Guide group name.
        description: Short description of its contents.
        href: Existing documentation destination.

    Returns:
        A native, keyboard-accessible navigation link.
    """
    return rx.el.a(
        rx.el.div(
            rx.el.span(title, class_name="text-base font-normal text-foreground"),
            rx.el.span(
                description,
                class_name="mt-1 block text-sm leading-6 text-muted-foreground",
            ),
            class_name="min-w-0",
        ),
        ui.icon("ArrowUpRight01Icon", size=18, aria_hidden=True),
        href=href,
        class_name=f"flex items-center justify-between gap-6 rounded-xl px-4 py-5 transition-colors hover:bg-muted motion-reduce:transition-none {FOCUS}",
    )


def hero() -> rx.Component:
    """Render the docs introduction using the marketing typography and actions."""
    return rx.el.section(
        rx.el.div(
            rx.el.h1(
                "Reflex Documentation",
                class_name="max-w-2xl font-heading text-4xl font-light leading-[1.04] tracking-[-0.045em] text-foreground text-balance sm:text-5xl lg:text-[64px]",
            ),
            rx.el.p(
                "Get up and running with Reflex in minutes. A complete set of resources "
                "to build, deploy, and scale your application.",
                class_name="max-w-xl text-base font-normal leading-7 text-muted-foreground sm:text-lg sm:leading-8",
            ),
            rx.el.div(
                rx.el.a(
                    button(
                        "Explore Framework",
                        variant="primary",
                        size="lg",
                        class_name="!px-6 !font-normal",
                        native_button=False,
                    ),
                    href=getting_started.introduction.path,
                    class_name=f"rounded-full {FOCUS}",
                ),
                rx.el.a(
                    button(
                        "Build with AI",
                        variant="ghost",
                        size="lg",
                        class_name="!border-0 !bg-muted !px-6 !font-normal !text-foreground !shadow-none hover:!bg-accent-hover",
                        native_button=False,
                    ),
                    href="/ai/",
                    class_name=f"rounded-full {FOCUS}",
                ),
                class_name="mt-2 flex flex-wrap items-center gap-x-7 gap-y-3",
            ),
            class_name="flex min-w-0 flex-col items-start gap-6",
        ),
        rx.el.nav(
            rx.el.p(
                "Find your next step",
                class_name="px-4 pb-2 text-sm text-muted-foreground",
            ),
            _guide(
                "Getting started",
                "Learn the framework and build your first app.",
                getting_started.introduction.path,
            ),
            _guide(
                "Component library",
                "Find the UI components for your application.",
                library.path,
            ),
            _guide(
                "Deploy your app",
                "Take your application from local to live.",
                hosting.deploy_quick_start.path,
            ),
            aria_label="Documentation starting points",
            class_name="min-w-0 border-t border-border-subtle pt-6 lg:border-t-0 lg:border-l lg:pl-8 lg:pt-0",
        ),
        style={
            "--docs-hero-header-height": rx.cond(
                HostingBannerState.is_banner_visible, "6.5rem", "4rem"
            )
        },
        class_name=f"docs-hero {CONTAINER} relative grid items-center gap-10 pb-12 sm:pb-16 lg:grid-cols-[1.45fr_1fr] lg:gap-16 lg:pb-20",
    )
