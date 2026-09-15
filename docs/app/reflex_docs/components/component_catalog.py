"""Shared category rows for the component catalogs."""

import reflex as rx


def component_category(
    title: str,
    href: str,
    description: str,
    links: list[tuple[str, str]],
) -> rx.Component:
    """Render an aligned category heading and a responsive list of guide links.

    Args:
        title: Category name.
        href: Category overview route.
        description: Component count or short category description.
        links: Display names and documentation routes.

    Returns:
        A component catalog section.
    """
    return rx.el.section(
        rx.link(
            rx.box(
                rx.el.h2(
                    title,
                    class_name="text-lg font-book leading-6 tracking-tight text-foreground transition-colors group-hover:text-muted-foreground",
                ),
                rx.text(
                    description,
                    class_name="text-xs font-normal leading-5 text-muted-foreground",
                ),
                class_name="flex min-w-0 flex-col gap-2",
            ),
            href=href,
            underline="none",
            class_name="group block rounded-compact text-foreground focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ring",
        ),
        rx.el.ul(
            *[
                rx.el.li(
                    rx.el.a(
                        label,
                        href=link,
                        class_name="block rounded-compact px-3 py-2 text-sm font-normal leading-6 text-muted-foreground decoration-border-strong underline-offset-4 hover:text-foreground hover:underline transition-colors focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-ring",
                    ),
                )
                for label, link in links
            ],
            class_name="grid min-w-0 grid-cols-2 gap-x-2 gap-y-1 xl:grid-cols-3 list-none m-0 p-0",
        ),
        class_name="docs-library-category grid grid-cols-1 items-start gap-5 border-t border-border-subtle -mx-4 px-4 py-7 md:items-baseline md:grid-cols-[minmax(0,1fr)_minmax(0,3fr)] md:gap-8",
    )
