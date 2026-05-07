import reflex as rx

from reflex_docs.pages.docs import enterprise as enterprise_page
from reflex_docs.pages.docs_landing.views.link_item import faded_borders, link_item


def enterprise_section() -> rx.Component:
    return rx.el.section(
        rx.el.div(
            rx.el.h2(
                "Enterprise",
                class_name="text-secondary-12 text-3xl font-[575]",
            ),
            rx.el.p(
                "Learn how to build enterprise-ready applications with Reflex.",
                class_name="text-secondary-11 text-sm font-[475]",
            ),
            class_name="flex flex-col gap-4",
        ),
        rx.el.div(
            faded_borders(),
            link_item(
                "MenuSquareIcon",
                "Components",
                "Explore reusable enterprise-grade Reflex UI components designed for scalability, security, and efficient development in complex business environments.",
                enterprise_page.ag_grid.index.path,
            ),
            link_item(
                "SquareLockPasswordIcon",
                "Extensible Auth",
                "Implement flexible and secure authentication and authorization systems tailored for enterprise requirements, with support for SSO, OAuth, and advanced access controls.",
                enterprise_page.overview.path,
                has_padding_left=True,
            ),
            class_name="grid grid-cols-1 lg:grid-cols-2 border-t border-secondary-4 relative",
        ),
        class_name="flex flex-col gap-10 max-lg:text-center relative max-w-(--docs-layout-max-width) mx-auto w-full justify-start lg:mb-24 mb-10 max-xl:px-6 overflow-hidden",
    )
