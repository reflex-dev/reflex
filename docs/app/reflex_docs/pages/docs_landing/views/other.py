import reflex as rx
from reflex_site_shared.constants import CONTRIBUTING_URL

from reflex_docs.pages.docs_landing.views.layout import SECTION, section_heading
from reflex_docs.pages.docs_landing.views.link_item import link_item


def other_section() -> rx.Component:
    from reflex_docs.pages.docs import wrapping_react

    return rx.el.section(
        section_heading(
            "Other", "Learn about other features and tools that Reflex offers."
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
        class_name=f"{SECTION} border-t border-border-subtle",
    )
