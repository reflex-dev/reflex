import reflex as rx
from reflex_ui_shared.constants import REFLEX_ASSETS_CDN
from reflex_ui_shared.meta.meta import create_meta_tags
from reflex_ui_shared.views.cta_card import cta_card
from reflex_ui_shared.views.footer import footer_index

from reflex_docs.pages.docs_landing.views import (
    ai_builder_section,
    divider,
    enterprise_section,
    framework,
    hero,
    hosting_section,
    other_section,
    self_hosting_section,
)
from reflex_docs.views.docs_navbar import docs_navbar


@rx.page(
    route="/docs",
    title="Reflex Documentation - Build Web Apps in Pure Python",
    meta=create_meta_tags(
        title="Reflex Documentation - Build Web Apps in Pure Python",
        description="Reflex documentation: tutorials, API reference, and guides for building full-stack Python web apps. Get started in minutes.",
        image=f"{REFLEX_ASSETS_CDN}previews/index_preview.webp",
        url="https://reflex.dev/docs",
    ),
)
def docs_landing() -> rx.Component:
    return rx.el.div(
        docs_navbar(),
        rx.el.main(
            rx.el.div(
                hero(),
                divider(class_name="max-w-full"),
                ai_builder_section(),
                framework(),
                enterprise_section(),
                hosting_section(),
                self_hosting_section(),
                other_section(),
                cta_card(),
                footer_index(),
                class_name="flex flex-col relative justify-center items-center w-full overflow-hidden",
            ),
            class_name="flex flex-col w-full relative h-full justify-center items-center",
        ),
        class_name="flex flex-col w-full justify-center items-center relative dark:bg-m-slate-12 bg-m-slate-1",
    )
