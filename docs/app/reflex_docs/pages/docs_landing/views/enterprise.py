import reflex as rx

from reflex_docs.pages.docs import enterprise as enterprise_page
from reflex_docs.pages.docs_landing.views.layout import SECTION
from reflex_docs.pages.docs_landing.views.link_item import link_item


def enterprise_section() -> rx.Component:
    return rx.el.section(
        rx.el.div(
            rx.el.h2(
                "Enterprise",
                class_name="font-heading text-3xl font-light leading-[1.12] tracking-[-0.035em] text-foreground sm:text-4xl",
            ),
            rx.el.p(
                "Learn how to build enterprise-ready applications with Reflex.",
                class_name="max-w-lg text-base font-normal leading-7 text-muted-foreground",
            ),
            class_name="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between lg:gap-12",
        ),
        rx.el.div(
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
            class_name="grid grid-cols-1 gap-4 lg:grid-cols-2",
        ),
        class_name=f"{SECTION} flex flex-col gap-8 border-t border-border-subtle sm:gap-10",
    )
