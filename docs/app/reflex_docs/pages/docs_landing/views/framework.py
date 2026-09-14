import reflex as rx
import reflex_components_internal as ui

from reflex_docs.pages.docs import database, enterprise, getting_started
from reflex_docs.pages.docs.library import library
from reflex_docs.pages.library_previews import core_components_dict


def docs_item(
    icon: str, title: str, description: str, href: str, enterprise_only: bool = False
) -> rx.Component:
    """Link to a framework guide with a quiet, readable text treatment."""
    return rx.el.a(
        rx.el.div(
            ui.icon(
                icon, class_name="size-5 shrink-0", stroke_width=1.5, aria_hidden=True
            ),
            rx.el.h3(
                title,
                class_name="text-xl font-book tracking-tight group-hover:underline decoration-border-strong underline-offset-4",
            ),
            rx.el.span(
                "Enterprise-only",
                class_name="ml-auto shrink-0 rounded-compact bg-muted px-2 py-1 text-xs font-normal text-muted-foreground",
            )
            if enterprise_only
            else None,
            class_name="flex flex-wrap items-center gap-3 text-foreground",
        ),
        rx.el.p(
            description,
            class_name="text-sm font-normal leading-6 text-muted-foreground",
        ),
        href=href,
        class_name="docs-framework-guide group flex flex-col gap-3 py-6 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ring",
    )


def links_section() -> rx.Component:
    """Show the three core framework guides as an open list."""
    return rx.el.div(
        docs_item(
            "SourceCodeSquareIcon",
            "How It Works",
            "Learn the basics of how Reflex works behind the scenes and how its architecture enables flexible, advanced usage.",
            getting_started.introduction.path,
        ),
        docs_item(
            "ShieldUserIcon",
            "Auth",
            "Implement secure authentication for your apps using Reflex’s built-in features and extensible architecture.",
            enterprise.auth.overview.path,
            enterprise_only=True,
        ),
        docs_item(
            "DatabaseIcon",
            "Database",
            "Manage and interact with your data seamlessly using Reflex’s straightforward models and querying approach.",
            database.overview.path,
        ),
        class_name="min-w-0 divide-y divide-border-subtle border-t border-border-subtle",
    )


def component_link(name: str, href: str) -> rx.Component:
    """Render a category link without button chrome or repeated arrows."""
    return rx.el.a(
        name,
        href=f"/library/{href.strip('/')}",
        class_name="docs-framework-category flex min-h-11 items-center border-b border-border px-0 py-3 text-sm font-normal leading-6 text-muted-foreground decoration-border-strong underline-offset-4 transition-colors hover:text-foreground hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring",
    )


def components_section() -> rx.Component:
    """Group component categories on the marketing theme's muted surface."""
    categories = [
        ("Data Display", "data-display"),
        ("Disclosure", "disclosure"),
        ("Dynamic Rendering", "dynamic_rendering"),
        ("Forms", "forms"),
        ("Layout", "layout"),
        ("Media", "media"),
        ("Other", "other"),
        ("Overlays", "overlays"),
        ("Tables and Data Grids", "tables_and_data_grids"),
        ("Typography", "typography"),
    ]
    return rx.el.div(
        rx.el.div(
            rx.el.h3(
                "Component Library",
                class_name="text-2xl font-book tracking-tight text-foreground",
            ),
            rx.el.p(
                "Build your app with our comprehensive collection of UI components and features.",
                class_name="max-w-md text-base font-normal leading-7 text-muted-foreground",
            ),
            class_name="flex flex-col gap-3",
        ),
        rx.el.div(
            *[
                component_link(name, core_components_dict[key]["path"])
                for name, key in categories
            ],
            class_name="grid grid-cols-1 gap-x-8 sm:grid-cols-2 lg:gap-x-10",
        ),
        rx.el.a(
            "Browse all components",
            rx.icon("arrow-right", class_name="size-4", aria_hidden=True),
            href=library.path,
            class_name="inline-flex min-h-11 w-fit items-center gap-2 rounded-compact text-sm font-book text-foreground transition-colors hover:text-muted-foreground focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ring",
        ),
        class_name="docs-framework-library flex min-w-0 flex-col gap-6 rounded-panel border border-border-subtle bg-muted p-6 sm:p-8 lg:p-10",
    )


def framework() -> rx.Component:
    """Introduce framework guides and the component catalog in an editorial layout."""
    return rx.el.section(
        rx.el.div(
            rx.el.h2(
                "Framework",
                id="docs-framework-title",
                class_name="text-foreground text-3xl font-book tracking-tight",
            ),
            rx.el.p(
                "Learn how to build applications with Reflex Framework.",
                class_name="text-muted-foreground text-sm font-normal",
            ),
            class_name="flex flex-col gap-4",
        ),
        rx.el.div(
            links_section(),
            components_section(),
            class_name="grid grid-cols-1 items-start gap-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,2fr)] lg:gap-12",
        ),
        aria_labelledby="docs-framework-title",
        class_name="docs-framework-section flex flex-col gap-10 max-w-(--landing-layout-max-width) mx-auto w-full lg:pt-24 pt-10 lg:mb-24 mb-10 max-xl:px-6",
    )
