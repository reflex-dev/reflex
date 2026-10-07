import reflex as rx
from reflex_site_shared.constants import OG_IMAGE_URL
from reflex_site_shared.route import Route
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


def _docs_landing() -> rx.Component:
    """Render the documentation homepage.

    Returns:
        The documentation landing page component.
    """
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


docs_landing = Route(
    path="/",
    title="Reflex Documentation - Build Web Apps in Pure Python",
    description="Reflex documentation: tutorials, API reference, and guides for building full-stack Python web apps. Get started in minutes.",
    image=OG_IMAGE_URL,
    component=_docs_landing,
)
