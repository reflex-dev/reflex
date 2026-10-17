import reflex as rx
import reflex_components_internal as ui
from reflex_site_shared.components.marketing_button import button

from reflex_docs.pages.docs import database, enterprise, getting_started
from reflex_docs.pages.docs.library import library
from reflex_docs.pages.docs_landing.views.layout import FOCUS, SECTION, section_heading
from reflex_docs.pages.library_previews import core_components_dict


def docs_item(
    icon: str, title: str, description: str, href: str, enterprise_only: bool = False
) -> rx.Component:
    return rx.el.a(
        rx.el.div(
            ui.icon(
                icon,
                class_name="size-5 shrink-0 text-foreground",
                stroke_width=1.5,
                aria_hidden=True,
            ),
            rx.el.h3(
                title,
                class_name="font-heading text-xl font-normal leading-7 tracking-[-0.025em] text-foreground",
            ),
            rx.el.div(
                "Enterprise-only",
                class_name="w-fit rounded-full border border-border px-2.5 py-1 text-xs font-normal text-muted-foreground",
            )
            if enterprise_only
            else None,
            ui.icon(
                "ArrowRight01Icon",
                class_name="ml-auto size-4 shrink-0 text-muted-foreground",
                aria_hidden=True,
            ),
            class_name="flex flex-wrap items-center gap-x-3 gap-y-2",
        ),
        rx.el.p(
            description,
            class_name="text-sm font-normal leading-6 text-muted-foreground",
        ),
        to=href,
        class_name=f"group flex min-w-0 flex-col gap-3 rounded-[20px] border border-border-subtle p-6 text-left transition-colors hover:bg-muted motion-reduce:transition-none {FOCUS}",
    )


def links_section() -> rx.Component:
    return rx.el.div(
        docs_item(
            "SourceCodeSquareIcon",
            "What You Can Build",
            "Start with working Python examples for linked charts, AI chat, model interfaces, and internal tools.",
            getting_started.what_you_can_build.path,
        ),
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
        class_name="grid min-w-0 grid-cols-1 gap-4 sm:grid-cols-2",
    )


def component_link(name: str, href: str) -> rx.Component:
    """Render a padded category link with matching hover and keyboard focus.

    Args:
        name: Category label.
        href: Category path relative to the component library.

    Returns:
        A single navigable row with an inset label and arrow.
    """
    return rx.el.a(
        rx.el.span(name),
        ui.icon(
            "ArrowRight01Icon", class_name="ml-auto size-4 shrink-0", aria_hidden=True
        ),
        to=f"/library/{href.strip('/')}/",
        class_name="flex min-h-11 w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-normal leading-6 text-foreground transition-colors hover:bg-background motion-reduce:transition-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring",
    )


def components_section() -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.div(
                ui.icon(
                    "MenuSquareIcon",
                    class_name="size-5",
                    stroke_width=1.5,
                    aria_hidden=True,
                ),
                rx.el.h3(
                    "Component Library",
                    class_name="font-heading text-2xl font-normal tracking-[-0.025em] text-foreground",
                ),
                class_name="flex items-center gap-3",
            ),
            rx.el.p(
                "Build your app with our comprehensive collection of UI components and features.",
                class_name="max-w-sm text-sm font-normal leading-6 text-muted-foreground",
            ),
            rx.el.a(
                button(
                    "Browse All Components",
                    variant="ghost",
                    native_button=False,
                    class_name="!border-0 !bg-background !font-normal !text-foreground !shadow-none hover:!bg-accent-hover",
                ),
                to=library.path,
                class_name=f"mt-3 w-fit rounded-full {FOCUS}",
            ),
            class_name="flex flex-col items-start gap-3",
        ),
        rx.el.div(
            rx.el.div(
                component_link(
                    "Data Display", core_components_dict["data-display"]["path"]
                ),
                component_link(
                    "Disclosure", core_components_dict["disclosure"]["path"]
                ),
                component_link(
                    "Dynamic Rendering",
                    core_components_dict["dynamic_rendering"]["path"],
                ),
                component_link("Forms", core_components_dict["forms"]["path"]),
                component_link("Layout", core_components_dict["layout"]["path"]),
                component_link("Media", core_components_dict["media"]["path"]),
                class_name="flex min-w-0 flex-col gap-1",
            ),
            rx.el.div(
                component_link("Other", core_components_dict["other"]["path"]),
                component_link("Overlays", core_components_dict["overlays"]["path"]),
                component_link(
                    "Tables And Data Grids Rendering",
                    core_components_dict["tables_and_data_grids"]["path"],
                ),
                component_link(
                    "Typography", core_components_dict["typography"]["path"]
                ),
                class_name="flex min-w-0 flex-col gap-1",
            ),
            class_name="grid grid-cols-1 gap-1 border-t border-border pt-5 sm:grid-cols-2 sm:gap-x-4",
        ),
        class_name="flex min-w-0 flex-col gap-7 rounded-[20px] bg-muted p-6 sm:p-8",
    )


def framework() -> rx.Component:
    return rx.el.section(
        section_heading(
            "Framework", "Learn how to build applications with Reflex Framework."
        ),
        rx.el.div(
            links_section(),
            components_section(),
            class_name="grid min-w-0 grid-cols-1 gap-4 lg:grid-cols-[1.1fr_1fr]",
        ),
        class_name=SECTION,
    )
