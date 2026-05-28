import reflex as rx
import reflex_components_internal as ui
from reflex_site_shared.components.marketing_button import button
from reflex_site_shared.constants import REFLEX_ASSETS_CDN

from reflex_docs.pages.docs import authentication, database, getting_started
from reflex_docs.pages.docs.library import library
from reflex_docs.pages.library_previews import core_components_dict


def docs_item(
    icon: str, title: str, description: str, href: str, enterprise_only: bool = False
) -> rx.Component:
    return rx.el.div(
        rx.el.div(
            ui.icon(
                icon,
                class_name="size-6 group-hover:text-primary-10 group-hover:dark:text-m-slate-5",
                stroke_width=1.5,
            ),
            rx.el.span(
                title,
                class_name="text-m-slate-12 dark:text-m-slate-3 text-xl font-[575] group-hover:text-primary-10 group-hover:dark:text-m-slate-5",
            ),
            rx.el.div(
                "Enterprise-only",
                class_name="text-m-slate-12 dark:text-m-slate-3 text-xs font-medium bg-m-slate-1 dark:bg-m-slate-11 px-2.5 h-7 border-b border rounded-lg border-m-slate-4 dark:border-m-slate-10 flex justify-center items-center ml-1",
            )
            if enterprise_only
            else None,
            ui.icon(
                "ArrowRight01Icon",
                class_name="size-4 ml-auto group-hover:text-primary-10 group-hover:dark:text-m-slate-5",
            ),
            class_name="flex row items-center gap-3 h-8",
        ),
        rx.el.p(
            description,
            class_name="text-m-slate-7 dark:text-m-slate-6 text-sm font-[475]",
        ),
        rx.el.a(to=href, class_name="absolute inset-0"),
        class_name="flex flex-col gap-2 py-8 pr-8 relative group lg:max-w-[21rem] w-full max-lg:text-start hover:bg-[linear-gradient(243deg,var(--m-slate-2,#F6F7F9)_0%,var(--m-slate-1,#FCFCFD)_100%)] dark:hover:bg-[linear-gradient(243deg,var(--m-slate-11,#1D2025)_0%,var(--m-slate-12,#151618)_63.63%)]",
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
            authentication.authentication_overview.path,
            enterprise_only=True,
        ),
        docs_item(
            "DatabaseIcon",
            "Database",
            "Manage and interact with your data seamlessly using Reflex’s straightforward models and querying approach.",
            database.overview.path,
        ),
        class_name="flex flex-col border-r border-y border-secondary-4 divide-y divide-secondary-4",
    )


def component_link(name: str, href: str) -> rx.Component:
    return rx.el.a(
        button(
            name,
            ui.icon("ArrowRight01Icon", class_name="ml-auto"),
            variant="ghost",
            size="xs",
            class_name="font-[525] w-full text-m-slate-12 dark:text-m-slate-3 px-0",
        ),
        to=f"/library/{href.strip('/')}",
        class_name="w-full",
    )


def components_section() -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.div(
                ui.icon("MenuSquareIcon", class_name="size-6", stroke_width=1.5),
                rx.el.span(
                    "Component Library",
                    class_name="text-m-slate-12 dark:text-m-slate-3 text-xl font-[575] group-hover:text-primary-10",
                ),
                class_name="flex row items-center gap-3 h-8",
            ),
            rx.el.p(
                "Build your app with our comprehensive collection of UI components and features.",
                class_name="text-m-slate-7 dark:text-m-slate-6 text-sm font-[475] max-w-[16.5rem]",
            ),
            rx.el.a(
                button(
                    "Browse All Components",
                    variant="outline",
                    native_button=False,
                    class_name="font-[525] w-fit text-m-slate-12 dark:text-m-slate-3",
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
        class_name="flex flex-col gap-4 lg:px-8 pt-8 max-lg:pr-8 pb-6 h-auto w-full flex-1 border-r border-m-slate-4 dark:border-m-slate-10 border-y",
    )


def squares_divider() -> rx.Component:
    return rx.el.div(
        rx.image(
            src=f"{REFLEX_ASSETS_CDN}common/{rx.color_mode_cond('light', 'dark')}/squares_vertical_docs.svg",
            alt="Squares Vertical Docs",
            loading="lazy",
            class_name="pointer-events-none w-auto h-full",
        ),
        class_name="flex p-4.5 h-auto border-r border-y border-m-slate-4 dark:border-m-slate-10 max-lg:hidden",
    )


def framework() -> rx.Component:
    return rx.el.section(
        rx.el.div(
            rx.el.h2(
                "Framework",
                class_name="text-m-slate-12 dark:text-m-slate-3 text-3xl font-[575]",
            ),
            rx.el.p(
                "Learn how to build applications with Reflex Framework.",
                class_name="text-m-slate-7 dark:text-m-slate-6 text-sm font-[475]",
            ),
            class_name="flex flex-col gap-4",
        ),
        rx.el.div(
            rx.el.div(
                class_name="absolute bottom-0 -left-24 w-24 h-px bg-gradient-to-r from-transparent to-current text-m-slate-4 dark:text-m-slate-10"
            ),
            rx.el.div(
                class_name="absolute top-0 -left-24 w-24 h-px bg-gradient-to-r from-transparent to-current text-m-slate-4 dark:text-m-slate-10"
            ),
            rx.el.div(
                class_name="absolute bottom-0 -right-24 w-24 h-px bg-gradient-to-l from-transparent to-current text-m-slate-4 dark:text-m-slate-10"
            ),
            rx.el.div(
                class_name="absolute right-0 -top-24 h-24 w-px bg-gradient-to-b from-transparent to-current text-m-slate-4 dark:text-m-slate-10"
            ),
            links_section(),
            squares_divider(),
            components_section(),
            class_name="flex flex-col lg:flex-row relative",
        ),
        class_name="flex flex-col gap-10 max-lg:text-center relative max-w-(--landing-layout-max-width) mx-auto w-full justify-start lg:mb-24 mb-10 max-xl:px-6 overflow-hidden",
    )
