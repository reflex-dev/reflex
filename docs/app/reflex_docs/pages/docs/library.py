import reflex as rx
from reflex.utils.format import to_snake_case, to_title_case

from reflex_docs.templates.docpage import docpage, h1_comp, h2_comp, text_comp_2


def get_display_name(name: str) -> str:
    normalized = to_snake_case(name)
    if normalized == "html":
        return "HTML"
    if normalized == "svg":
        return "SVG"
    return to_title_case(normalized, sep=" ")


HTML_COMPONENT_ORDER = {
    "html": 0,
    "text": 1,
    "layout": 2,
    "forms": 3,
    "media": 4,
    "tables": 5,
    "svg": 6,
}


def get_components_for_category(category: str, components: list) -> list:
    if to_snake_case(category) != "html":
        return components
    return sorted(
        components,
        key=lambda component: HTML_COMPONENT_ORDER.get(
            to_snake_case(component[0]), len(HTML_COMPONENT_ORDER)
        ),
    )


def component_grid():
    from reflex_docs.pages.docs import component_list, graphing_components
    from reflex_docs.templates.docpage.sidebar.sidebar_items import get_component_link

    def generate_gallery(
        components,
        prefix: str = "",
    ):
        sidebar = [
            rx.el.section(
                rx.el.a(
                    rx.el.h2(
                        get_display_name(category),
                        class_name="m-0 text-base font-medium leading-6",
                    ),
                    rx.icon(
                        "chevron-right",
                        aria_hidden=True,
                        class_name="size-3.5 shrink-0 opacity-0 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100",
                    ),
                    href=f"/library/{prefix.strip('/') + '/' if prefix.strip('/') else ''}{category.lower()}/",
                    class_name="group flex min-h-8 w-fit items-center gap-2 self-start text-foreground no-underline transition-colors hover:text-muted-foreground focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ring",
                ),
                rx.el.ul(
                    *[
                        rx.el.li(
                            rx.el.a(
                                get_display_name(c[0]),
                                href=get_component_link(
                                    category=category,
                                    clist=c,
                                    prefix=prefix,
                                ),
                                class_name="inline-flex min-h-8 items-center text-sm font-book leading-6 text-muted-foreground no-underline transition-colors hover:text-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring",
                            ),
                        )
                        for c in get_components_for_category(
                            category, components[category]
                        )
                    ],
                    class_name="m-0 grid w-full min-w-0 max-w-[48rem] list-none grid-cols-1 gap-x-4 gap-y-1 p-0 sm:grid-cols-2 xl:grid-cols-3",
                ),
                class_name="grid grid-cols-1 gap-3 border-b border-border py-6 md:grid-cols-[12rem_minmax(0,1fr)] md:gap-6",
            )
            for category in components
        ]

        return sidebar

    core = generate_gallery(
        components=component_list,
    )
    # add `graphing/` prefix when generating graphing components to assume the url `/library/graphing/<category>/<component>`.
    graphs = generate_gallery(
        components=graphing_components,
        prefix="/graphing/",
    )
    return rx.box(
        rx.box(
            *core,
            class_name="border-t border-border",
        ),
        rx.box(
            h2_comp(
                text="Graphing Components",
            ),
            text_comp_2(
                text="Discover our range of components for building interactive charts and data visualizations. Create clear, informative, and visually engaging representations of your data with ease.",
            ),
            rx.box(
                *graphs,
                class_name="mt-6 border-t border-border",
            ),
            class_name="flex flex-col",
        ),
        class_name="w-full flex flex-col gap-16",
    )


@docpage(
    set_path="/library/",
    right_sidebar=True,
    pseudo_right_bar=True,
)
def library():
    return rx.box(
        h1_comp(
            text="Component Library",
        ),
        text_comp_2(
            text="Components let you split the UI into independent, reusable pieces, and think about each piece in isolation. This page contains a list of all builtin components.",
        ),
        component_grid(),
        rx.el.p(
            "Connect your components to data and events with the ",
            rx.el.a(
                "state guides",
                href="/library/state/",
                class_name="docs-text-link underline underline-offset-4",
            ),
            ".",
            class_name="mt-8 text-sm leading-6 text-muted-foreground",
        ),
        class_name="flex flex-col h-full mb-12",
    )
