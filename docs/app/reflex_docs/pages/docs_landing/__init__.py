import reflex as rx
from reflex_site_shared.constants import OG_IMAGE_URL
from reflex_site_shared.meta.meta import create_meta_tags
from reflex_site_shared.views.marketing_footer import marketing_footer

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
from reflex_docs.pages.docs_landing.views.cta import docs_cta
from reflex_docs.views.docs_navbar import docs_navbar


@rx.page(
    route="/",
    title="Reflex Documentation - Build Web Apps in Pure Python",
    # og:image is emitted once by the compiler from `image`; drop it from the
    # create_meta_tags list to avoid a favicon-default + preview duplicate.
    image=OG_IMAGE_URL,
    meta=[
        m
        for m in create_meta_tags(
            title="Reflex Documentation - Build Web Apps in Pure Python",
            description="Reflex documentation: tutorials, API reference, and guides for building full-stack Python web apps. Get started in minutes.",
            image=OG_IMAGE_URL,
            url="https://reflex.dev/docs/",
        )
        if not (isinstance(m, dict) and m.get("property") == "og:image")
    ],
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
                docs_cta(),
                marketing_footer(show_color_mode_toggle=True),
                class_name="flex flex-col relative justify-center items-center w-full overflow-hidden",
            ),
            class_name="flex flex-col w-full relative h-full justify-center items-center",
        ),
        class_name="flex flex-col w-full justify-center items-center relative bg-background",
    )
