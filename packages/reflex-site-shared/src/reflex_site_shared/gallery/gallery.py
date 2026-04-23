"""Gallery module."""

import re

import reflex_components_internal as ui

import reflex as rx
from reflex_site_shared.constants import INTEGRATIONS_IMAGES_URL, REFLEX_ASSETS_CDN
from reflex_site_shared.gallery.r_svg_loader import r_svg_loader
from reflex_site_shared.templates.webpage import webpage
from reflex_site_shared.utils.md import MarkdownDocument, get_md_files

REFLEX_BUILD_TEMPLATES_PATH = "reflex_build_templates/"
REFLEX_BUILD_TEMPLATES_IMAGES = "reflex_build_template_images/"


def get_templatey_apps(paths: list):
    """Method to parse each markdown file and return the data from the file.

    Returns:
        The component.
    """
    gallery_apps = {}
    for path in sorted(paths, reverse=True):
        document = MarkdownDocument.from_file(path)
        key = str(path).replace(".md", "/")
        gallery_apps[key] = document
    return gallery_apps


paths = get_md_files(REFLEX_BUILD_TEMPLATES_PATH)
template_apps_data = get_templatey_apps(paths)


def app_dialog_with_trigger(
    app_url: str,
    app_name: str,
    app_author: str,
    app_thread: str,
    app_inner_page: str,
    trigger_content: rx.Component,
    app_video_url: str,
):
    """App dialog with trigger.

    Returns:
        The component.
    """
    return rx.dialog.root(
        rx.dialog.trigger(trigger_content, class_name="w-full h-full"),
        rx.dialog.content(
            rx.el.div(
                rx.el.div(
                    r_svg_loader(),
                    class_name="absolute inset-0 flex items-center justify-center",
                ),
                rx.el.div(
                    rx.el.div(
                        rx.el.p(
                            app_name, class_name="text-md !text-slate-11 font-bold"
                        ),
                        rx.el.p(app_author, class_name="text-sm !text-slate-9"),
                        class_name="flex flex-row gap-x-2 items-center",
                    ),
                    rx.link(
                        ui.button(
                            "Learn More",
                            variant="secondary",
                            size="md",
                            class_name="!text-secondary-12",
                        ),
                        href=app_inner_page,
                        class_name="no-underline outline-none",
                    ),
                    class_name="flex flex-row items-center justify-between",
                ),
                rx.el.iframe(
                    src=app_video_url,
                    class_name="w-full h-full xl:rounded-md shadow-small z-10",
                    id="iFrame",
                    title="Reflex Build",
                    frameborder="0",
                ),
                class_name="flex flex-col w-full h-full gap-y-3 relative",
            ),
            class_name="w-full !max-w-[90em] xl:max-w-[110em] 2xl:max-w-[120em] h-[80vh] font-sans",
        ),
    )


def integration_image(integration: str, class_name: str = ""):
    """Integration image.

    Returns:
        The component.
    """
    integration_logo = integration.replace(" ", "_").lower()
    return ui.avatar.root(
        ui.avatar.image(
            src=rx.color_mode_cond(
                f"{INTEGRATIONS_IMAGES_URL}light/{integration_logo}.svg",
                f"{INTEGRATIONS_IMAGES_URL}dark/{integration_logo}.svg",
            ),
            unstyled=True,
            class_name="size-full",
        ),
        ui.avatar.fallback(
            unstyled=True,
        ),
        unstyled=True,
        class_name=ui.cn("size-4 flex items-center justify-center", class_name),
    )


def integrations_stack(integrations: list[str]) -> rx.Component:
    """Integrations stack.

    Returns:
        The component.
    """
    return rx.el.div(
        rx.foreach(
            integrations,
            lambda integration: rx.el.div(
                ui.tooltip(
                    trigger=rx.el.div(
                        integration_image(integration, class_name="size-4"),
                        class_name="size-8 shrink-0 flex justify-center items-center rounded-full shadow-small border border-secondary-a5 bg-white-1 dark:bg-secondary-1 cursor-default",
                    ),
                    side="bottom",
                    content=integration,
                ),
            ),
        ),
        class_name="flex flex-row -space-x-2 flex-wrap gap-y-2",
    )


def extended_gallery_grid_item(
    app_url: str,
    app_name: str,
    app_author: str,
    app_thread: str,
    app_image: str,
    app_inner_page: str,
    app_video_url: str,
    app_integrations: list[str],
):
    """Extended gallery grid item.

    Returns:
        The component.
    """
    return app_dialog_with_trigger(
        app_url=app_url,
        app_author=app_author,
        app_name=app_name,
        app_thread=app_thread,
        app_inner_page=app_inner_page,
        app_video_url=app_video_url,
        trigger_content=rx.el.div(
            rx.el.div(
                rx.el.div(
                    rx.image(
                        src=app_image,
                        class_name="group-hover:scale-105 duration-200 ease-out object-center object-cover absolute inset-0 size-full blur-in transition-all z-10",
                    ),
                    rx.el.div(
                        rx.el.div(
                            rx.link(
                                ui.button(
                                    "Learn More",
                                    variant="secondary",
                                    size="md",
                                    class_name="w-full !text-secondary-12",
                                    on_click=rx.stop_propagation,
                                ),
                                href=app_inner_page,
                                class_name="no-underline flex-1",
                                on_click=rx.stop_propagation,
                            ),
                            ui.button(
                                "Preview",
                                variant="primary",
                                size="md",
                                class_name="flex-1 shadow-none border-none",
                            ),
                            class_name="flex flex-row gap-x-2 w-full items-stretch px-4 pb-4",
                        ),
                        class_name="absolute inset-0 flex items-end justify-center opacity-0 translate-y-2 group-hover:opacity-100 group-hover:translate-y-0 transition-all duration-300 ease-out pointer-events-none group-hover:pointer-events-auto z-[99]",
                    ),
                    class_name="overflow-hidden relative size-full aspect-video ease-out transition-all outline-none ",
                ),
                rx.el.div(
                    rx.el.span(
                        app_name,
                        class_name="text-sm font-semibold text-slate-12 dark:text-m-slate-3 truncate min-w-0 max-w-[90%]",
                    ),
                    rx.el.div(
                        rx.el.span(
                            "App Integrations: ",
                            class_name="text-slate-9 text-sm font-medium",
                        ),
                        rx.el.div(
                            integrations_stack(app_integrations),
                            class_name="flex flex-row gap-3.5 items-center flex-wrap",
                        ),
                        class_name="flex flex-row items-center gap-2 mt-2",
                    ),
                    class_name=(
                        "flex flex-col w-full px-4 py-3 border-t border-m-slate-4 dark:border-m-slate-12 gap-2 relative pb-4",
                    ),
                ),
                class_name="flex flex-col w-full",
            ),
            key=app_name,
            class_name="group cursor-pointer rounded-2xl shadow-small border border-slate-4 dark:border-m-slate-12 bg-white-1 dark:bg-m-slate-14 flex flex-col w-full relative overflow-hidden",
        ),
    )


def create_grid_with_items():
    """Create grid with items.

    Returns:
        The component.
    """
    items = []
    for document in template_apps_data.values():
        meta = document.metadata
        app_url = meta.get("demo", "#")
        app_name = meta.get("title", "Untitled").replace("_", " ").title()
        app_author = meta.get("author", "Team Reflex")
        app_thread = f"/gen/{app_name.lower().replace(' ', '-')}/"
        app_image = meta.get("image", "")
        slug = re.sub(r"[\s_]+", "-", meta.get("title", "")).lower()
        app_inner_page = f"/templates/{slug}"
        app_video_url = meta.get("video", "#")
        app_integrations = meta.get("integrations", [])

        items.append(
            extended_gallery_grid_item(
                app_url=app_url,
                app_name=app_name,
                app_author=app_author,
                app_thread=app_thread,
                app_image=f"{REFLEX_ASSETS_CDN}{REFLEX_BUILD_TEMPLATES_IMAGES}{app_image}",
                app_inner_page=app_inner_page,
                app_video_url=app_video_url,
                app_integrations=app_integrations,
            )
        )

    return rx.el.div(
        *items,
        class_name="grid grid-cols-1 sm:grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 md:px-8 lg:px-8",
    )


def create_header():
    """Create header.

    Returns:
        The component.
    """
    return rx.box(
        rx.box(
            rx.el.h1(
                "Reflex Build Templates",
                class_name="text-slate-12 text-4xl font-bold mb-6",
            ),
            rx.el.p(
                "Production-ready app templates built with Reflex — explore dashboards, tools, and AI-powered apps.",
                class_name="text-slate-11 text-lg leading-relaxed mb-12 max-w-lg font-medium",
            ),
            class_name="mb-8 lg:mb-0 text-center",
        ),
        class_name="flex flex-col justify-center items-center gap-6 w-full text-center",
    )


@webpage(
    path="/templates",
    title="Reflex App Templates - Python Dashboards & Tools",
    description="Reflex app templates: dashboards, chatbots, data tools, and AI apps. Start from a template and customize in Python.",
)
def gallery() -> rx.Component:
    """Gallery.

    Returns:
        The component.
    """
    return rx.el.section(
        rx.box(
            create_header(),
            create_grid_with_items(),
            class_name="w-full !max-w-[94.5rem] mx-auto",
        ),
        id="gallery",
        class_name="w-full px-4 pt-24 lg:pt-52 mt-4 mb-20",
    )
