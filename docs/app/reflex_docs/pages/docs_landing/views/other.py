import reflex as rx
from reflex_site_shared.constants import CONTRIBUTING_URL

from reflex_docs.pages.docs.custom_components import custom_components
from reflex_docs.pages.docs_landing.views.link_item import faded_borders, link_item


def other_section() -> rx.Component:
    return rx.el.section(
        rx.el.div(
            rx.el.h2(
                "Other",
                class_name="text-secondary-12 text-3xl font-[575]",
            ),
            rx.el.p(
                "Learn about other features and tools that Reflex offers.",
                class_name="text-secondary-11 text-sm font-[475]",
            ),
            class_name="flex flex-col gap-4",
        ),
        rx.el.div(
            link_item(
                "GitCommitIcon",
                "Contributing",
                "Learn how to contribute code, report issues, and help improve Reflex. Find guidelines and resources to get started with open-source development.",
                CONTRIBUTING_URL,
            ),
            link_item(
                "ReactIcon",
                "Extending with React Components",
                "See how to create and integrate your own React components into Reflex apps, allowing you to customize and extend your project’s capabilities.",
                custom_components.path,
                has_padding_left=True,
            ),
            faded_borders(),
            class_name="grid grid-cols-1 lg:grid-cols-2 border-t border-secondary-4 relative",
        ),
        class_name="flex flex-col gap-10 max-lg:text-center relative max-w-(--landing-layout-max-width) mx-auto w-full justify-start lg:mb-24 mb-10 max-xl:px-6 overflow-hidden",
    )
