import reflex as rx
from reflex_site_shared.constants import CONTRIBUTING_URL

from reflex_docs.pages.docs_landing.views.layout import SECTION
from reflex_docs.pages.docs_landing.views.link_item import link_item


def other_section() -> rx.Component:
    from reflex_docs.pages.docs import wrapping_react

    return rx.el.section(
        rx.el.div(
            rx.el.h2(
                "Other",
                class_name="font-heading text-3xl font-light leading-[1.12] tracking-[-0.035em] text-foreground sm:text-4xl",
            ),
            rx.el.p(
                "Learn about other features and tools that Reflex offers.",
                class_name="max-w-lg text-base font-normal leading-7 text-muted-foreground",
            ),
            class_name="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between lg:gap-12",
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
                wrapping_react.overview.path,
                has_padding_left=True,
            ),
            class_name="grid grid-cols-1 gap-4 lg:grid-cols-2",
        ),
        class_name=f"{SECTION} flex flex-col gap-8 border-t border-border-subtle sm:gap-10",
    )
