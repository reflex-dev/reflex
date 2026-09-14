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
        categories = [
            rx.el.section(
                rx.link(
                    rx.box(
                        rx.el.h2(
                            get_display_name(category),
                            class_name="text-lg font-book leading-6 tracking-tight text-foreground transition-colors group-hover:text-muted-foreground",
                        ),
                        rx.text(
                            f"{len(components[category])} components",
                            class_name="text-xs font-normal leading-5 text-muted-foreground",
                        ),
                        class_name="flex min-w-0 flex-col gap-2",
                    ),
                    href=f"/library/{prefix.strip('/') + '/' if prefix.strip('/') else ''}{category.lower()}",
                    underline="none",
                    class_name="group block rounded-compact text-foreground focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ring",
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
                                class_name="block rounded-compact px-3 py-2 text-sm font-normal leading-6 text-muted-foreground decoration-border-strong underline-offset-4 hover:text-foreground hover:underline transition-colors focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-ring",
                            ),
                        )
                        for c in get_components_for_category(
                            category, components[category]
                        )
                    ],
                    class_name="grid min-w-0 grid-cols-2 gap-x-2 gap-y-1 xl:grid-cols-3 list-none m-0 p-0",
                ),
                class_name="docs-library-category grid grid-cols-1 items-start gap-5 border-t border-border-subtle -mx-4 px-4 py-7 md:items-baseline md:grid-cols-[minmax(0,1fr)_minmax(0,3fr)] md:gap-8",
            )
            for category in components
        ]

        return categories

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
            class_name="flex flex-col",
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
                class_name="flex flex-col",
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
        class_name="flex flex-col h-full mb-12",
    )
