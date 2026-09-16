import reflex as rx
import reflex_components_internal as ui
from reflex_site_shared.components.marketing_button import button

from reflex_docs.pages.docs import database, enterprise, getting_started
from reflex_docs.pages.docs.library import library
from reflex_docs.pages.library_previews import core_components_dict


def docs_item(
    icon: str, title: str, description: str, href: str, enterprise_only: bool = False
) -> rx.Component:
    return rx.el.a(
        rx.el.div(
            ui.icon(
                icon,
                class_name="size-6 group-hover:text-primary-hover group-hover:dark:text-muted-foreground",
                stroke_width=1.5,
            ),
            rx.el.span(
                title,
                class_name="text-foreground text-xl font-[575] group-hover:text-primary-hover group-hover:dark:text-muted-foreground",
            ),
            rx.el.div(
                "Enterprise-only",
                class_name="text-foreground text-xs font-medium bg-background px-2.5 h-7 border-b border rounded-lg border-border-subtle flex justify-center items-center ml-1",
            )
            if enterprise_only
            else None,
            ui.icon(
                "ArrowRight01Icon",
                class_name="size-4 ml-auto group-hover:text-primary-hover group-hover:dark:text-muted-foreground",
            ),
            class_name="flex row items-center gap-3 h-8",
        ),
        rx.el.p(
            description,
            class_name="text-muted-foreground text-sm font-[475]",
        ),
        to=href,
        class_name="flex flex-col gap-2 py-8 pr-8 relative group focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring lg:max-w-[21rem] w-full max-lg:text-start hover:bg-[linear-gradient(243deg,var(--muted)_0%,var(--background)_100%)]",
    )


def links_section() -> rx.Component:
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
        class_name="flex flex-col border-r border-y border-border-subtle divide-y divide-border-subtle",
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
        ui.icon("ArrowRight01Icon", class_name="ml-auto size-4 shrink-0"),
        to=f"/library/{href.strip('/')}",
        class_name="flex min-h-9 w-full items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium text-foreground transition-colors hover:bg-accent focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring",
    )


def components_section() -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.div(
                ui.icon("MenuSquareIcon", class_name="size-6", stroke_width=1.5),
                rx.el.span(
                    "Component Library",
                    class_name="text-foreground text-xl font-[575] group-hover:text-primary-hover",
                ),
                class_name="flex row items-center gap-3 h-8",
            ),
            rx.el.p(
                "Build your app with our comprehensive collection of UI components and features.",
                class_name="text-muted-foreground text-sm font-[475] max-w-[16.5rem]",
            ),
            rx.el.a(
                button(
                    "Browse All Components",
                    variant="outline",
                    native_button=False,
                    class_name="font-[525] w-fit text-foreground",
                ),
                to=library.path,
                class_name="w-fit mt-4",
            ),
            class_name="flex flex-col gap-2 max-lg:text-start",
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
                class_name="flex flex-col gap-2",
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
                class_name="flex flex-col gap-2",
            ),
            class_name="grid grid-cols-1 lg:grid-cols-2 lg:gap-28 gap-10 mt-auto",
        ),
        class_name="flex flex-col gap-4 lg:px-8 pt-8 max-lg:pr-8 pb-6 h-auto w-full flex-1 border-r border-border-subtle border-y",
    )


def framework() -> rx.Component:
    return rx.el.section(
        rx.el.div(
            rx.el.h2(
                "Framework",
                class_name="text-foreground text-3xl font-medium",
            ),
            rx.el.p(
                "Learn how to build applications with Reflex Framework.",
                class_name="text-muted-foreground text-sm font-[475]",
            ),
            class_name="flex flex-col gap-4",
        ),
        rx.el.div(
            rx.el.div(
                class_name="absolute bottom-0 -left-24 w-24 h-px bg-gradient-to-r from-transparent to-current text-border-subtle"
            ),
            rx.el.div(
                class_name="absolute top-0 -left-24 w-24 h-px bg-gradient-to-r from-transparent to-current text-border-subtle"
            ),
            rx.el.div(
                class_name="absolute bottom-0 -right-24 w-24 h-px bg-gradient-to-l from-transparent to-current text-border-subtle"
            ),
            rx.el.div(
                class_name="absolute right-0 -top-24 h-24 w-px bg-gradient-to-b from-transparent to-current text-border-subtle"
            ),
            links_section(),
            components_section(),
            class_name="flex flex-col lg:flex-row relative",
        ),
        class_name="flex flex-col gap-10 max-lg:text-center relative max-w-(--landing-layout-max-width) mx-auto w-full justify-start pt-10 lg:pt-24 lg:mb-24 mb-10 max-xl:px-6 overflow-hidden",
    )
