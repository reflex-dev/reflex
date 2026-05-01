"""Apps module."""

import copy
import re

import reflex_components_internal as ui
from reflex_components_internal.blocks.demo_form import demo_form_dialog

import reflex as rx
from reflex_site_shared.components.blocks.flexdown import markdown
from reflex_site_shared.components.code_card import gallery_app_card
from reflex_site_shared.components.icons import get_icon
from reflex_site_shared.constants import REFLEX_ASSETS_CDN, SCREENSHOT_BUCKET
from reflex_site_shared.gallery.common import MarkdownDocument
from reflex_site_shared.gallery.gallery import integrations_stack
from reflex_site_shared.templates.gallery_app_page import gallery_app_page

GALLERY_APP_SOURCES = [
    ("templates/", "docs/getting-started/open-source-templates/"),
    ("reflex_build_templates/", "templates/"),
]


def integration_image(integration: str):
    """Integration image.

    Returns:
        The component.
    """
    integration_logo = integration.replace(" ", "_").lower()
    return ui.tooltip(
        trigger=ui.avatar.root(
            ui.avatar.image(
                src=rx.color_mode_cond(
                    f"{REFLEX_ASSETS_CDN}integrations/light/{integration_logo}.svg",
                    f"{REFLEX_ASSETS_CDN}integrations/dark/{integration_logo}.svg",
                ),
                unstyled=True,
                class_name="size-full",
            ),
            ui.avatar.fallback(
                unstyled=True,
            ),
            unstyled=True,
            class_name="size-5 flex items-center justify-center",
        ),
        content=integration,
    )


def load_all_gallery_apps():
    """Load markdown files from all supported paths and associate them with their base folder.

    Returns:
        The component.
    """
    from reflex_site_shared.utils.md import MarkdownDocument, get_md_files

    gallery_apps: dict[tuple[str, str], MarkdownDocument] = {}
    for folder, _ in GALLERY_APP_SOURCES:
        paths = get_md_files(folder)
        for path in sorted(paths, reverse=True):
            document = MarkdownDocument.from_file(path)
            document.metadata["title"] = document.metadata.get("title", "Untitled")
            clean_path = str(path).replace(".md", "/")
            gallery_apps[clean_path, folder] = document
    return gallery_apps


gallery_apps_data = load_all_gallery_apps()
gallery_apps_data_copy = {path: doc for (path, _), doc in gallery_apps_data.items()}
gallery_apps_data_open_source = {
    (path, folder): doc
    for (path, folder), doc in load_all_gallery_apps().items()
    if folder == "templates/"
}


def more_posts(current_post: dict) -> rx.Component:
    """More posts.

    Returns:
        The component.
    """
    posts = []
    app_copy = copy.deepcopy(gallery_apps_data)
    app_items = list(app_copy.items())
    current_index = next(
        (
            i
            for i, (path, document) in enumerate(app_items)
            if document.metadata.get("title") == current_post.get("title")
        ),
        None,
    )

    if current_index is None:
        selected_posts = app_items[-3:]
    else:
        other_posts = app_items[:current_index] + app_items[current_index + 1 :]
        if len(other_posts) <= 3:
            selected_posts = other_posts
        elif current_index == 0:
            selected_posts = other_posts[:3]
        elif current_index >= len(app_items) - 1:
            selected_posts = other_posts[-3:]
        else:
            if current_index < len(app_items) - 2:
                selected_posts = other_posts[current_index - 1 : current_index + 2]
            else:
                selected_posts = other_posts[current_index - 2 : current_index + 1]

    for path, document in selected_posts:
        if not path[0].startswith("reflex_build_templates/"):
            posts.append(gallery_app_card(app=document.metadata))

    return rx.el.section(
        rx.box(
            rx.el.h2("More Templates", class_name="font-large text-slate-12"),
            rx.el.elements.a(
                rx.box(
                    rx.text(
                        "View All", class_name="font-small text-slate-9 text-nowrap"
                    ),
                    get_icon(icon="new_tab", class_name=""),
                    class_name="flex items-center gap-1.5 border-slate-5 bg-slate-1 hover:bg-slate-3 shadow-small px-1.5 py-0.5 border rounded-md w-auto max-w-full text-slate-9 transition-bg cursor-pointer overflow-hidden border-solid",
                ),
                underline="none",
                href="/docs/getting-started/open-source-templates/",
            ),
            class_name="flex flex-row items-center justify-between gap-4",
        ),
        rx.box(
            *posts,
            class_name="gap-6 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 [&>*]:min-w-[300px] w-full mb-4 blog-grid",
        ),
        class_name="flex flex-col gap-10 mt-20 p-8 border-t border-slate-3",
    )


def page(document: MarkdownDocument, is_reflex_template: bool) -> rx.Component:
    """Render a detailed app page based on source type.

    Returns:
        The component.
    """
    meta = document.metadata

    image_component = (
        rx.image(
            src=meta["image"],
            alt=f"Image for Reflex App: {meta['title']}",
            loading="lazy",
            class_name="w-full object-cover max-w-full aspect-[1500/938] border-y border-slate-3 border-solid",
        )
        if not is_reflex_template
        else rx.el.div(
            rx.box(
                rx.el.h1(
                    meta["title"].replace("_", " ").title(),
                    class_name="font-x-large text-slate-12 text-left",
                ),
                class_name="w-full self-start pl-4",
            ),
            rx.el.iframe(
                src=meta["video"],
                class_name="w-full h-full xl:rounded-md shadow-small",
                id="iFrame",
                title="Reflex Build",
                frameborder="0",
            ),
            class_name="w-full h-[80vh] text-center flex flex-col gap-y-4 items-center text-slate-10",
        )
    )

    back_route_origin = (
        "/getting-started/open-source-templates/"
        if not is_reflex_template
        else "/templates/"
    )

    return rx.el.section(
        rx.el.article(
            image_component,
            rx.box(
                rx.el.header(
                    rx.link(
                        rx.box(
                            get_icon("arrow_right", class_name="rotate-180"),
                            "Back to Templates",
                            class_name="box-border flex justify-center items-center gap-2 bg-slate-1 py-0.5 font-small text-slate-9 transition-color cursor-pointer hover:text-slate-11 mb-6",
                        ),
                        underline="none",
                        class_name="flex w-fit",
                        href=back_route_origin,
                    ),
                    (
                        rx.el.h1(meta["title"], class_name="font-x-large text-slate-12")
                        if not is_reflex_template
                        else rx.fragment()
                    ),
                    rx.el.h2(meta["description"], class_name="font-md text-slate-11"),
                    (
                        rx.el.div(
                            rx.el.span(
                                "Integrations: ", class_name="text-slate-9 font-base"
                            ),
                            rx.el.div(
                                integrations_stack(meta.get("integrations", [])),
                                class_name="flex flex-row gap-3.5 items-center",
                            ),
                            class_name="flex flex-row items-center gap-2 mt-2",
                        )
                        if meta.get("integrations")
                        else rx.fragment()
                    ),
                    class_name="flex flex-col gap-3 p-8",
                ),
                rx.box(
                    *([
                        rx.box(
                            demo_form_dialog(
                                trigger=ui.button(
                                    ui.icon("LinkSquare01Icon"),
                                    "Book a Demo",
                                    class_name="flex-row-reverse gap-2 !w-full",
                                ),
                            ),
                            class_name="flex justify-center items-center h-full !w-full [&_button]:!w-full",
                        )
                    ]),
                    (
                        rx.link(
                            ui.button(
                                "View Code", variant="secondary", class_name="!w-full"
                            ),
                            is_external=True,
                            href=meta.get("source", "#"),
                        )
                        if not is_reflex_template
                        else rx.fragment()
                    ),
                    (
                        rx.cond(
                            "Reflex" in meta["author"],
                            rx.box(
                                rx.text(
                                    "Created by", class_name="text-slate-9 font-base"
                                ),
                                get_icon(icon="badge_logo"),
                                rx.text(
                                    meta["author"], class_name="text-slate-9 font-base"
                                ),
                                class_name="flex flex-row items-center gap-1 self-end",
                            ),
                            rx.text(
                                f"by {meta['author']}",
                                class_name="text-slate-9 font-base",
                            ),
                        )
                        if not is_reflex_template
                        else rx.fragment()
                    ),
                    class_name="p-8 flex flex-col gap-4",
                ),
                class_name="grid grid-cols-1 lg:grid-cols-2 divide-y lg:divide-y-0 lg:divide-x divide-slate-3 border-b border-slate-3",
            ),
            rx.box(
                markdown(document.content),
                class_name="flex flex-col gap-4 w-full p-8",
            ),
            more_posts(meta) if not is_reflex_template else rx.fragment(),
            class_name="flex flex-col max-w-full",
        ),
    )


gallery_apps_routes = []
for (_path, source_folder), document in gallery_apps_data.items():
    is_reflex_template = source_folder.startswith("reflex_build_templates")
    base_url = (
        "templates/" if is_reflex_template else "getting-started/open-source-templates/"
    )
    slug = re.sub(r"[\s_]+", "-", document.metadata["title"]).lower()
    route = f"/{base_url}{slug}"

    document.metadata["image"] = (
        f"{REFLEX_ASSETS_CDN}reflex_build_template_images/{document.metadata['image']}"
        if is_reflex_template and not document.metadata.get("ai_template", False)
        else f"{REFLEX_ASSETS_CDN}templates/{document.metadata['image']}"
        if not document.metadata.get("ai_template", False)
        else f"{SCREENSHOT_BUCKET}{document.metadata['image']}"
    )

    comp = gallery_app_page(
        path=route,
        title=document.metadata["title"],
        description=document.metadata.get("description", ""),
        image=document.metadata["image"],
        demo=document.metadata.get("demo"),
        meta=document.metadata.get("meta", []),
    )(lambda doc=document, is_rt=is_reflex_template: page(doc, is_rt))

    gallery_apps_routes.append(comp)
