import reflex as rx
from reflex.utils.format import to_snake_case, to_title_case
from reflex_site_shared.components.icons import get_icon

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
            rx.box(
                rx.link(
                    rx.el.h2(
                        get_display_name(category),
                        class_name="text-lg font-book leading-6 tracking-tight text-foreground",
                    ),
                    get_icon("new_tab", class_name="text-secondary-11 [&>svg]:size-4"),
                    href=f"/library/{prefix.strip('/') + '/' if prefix.strip('/') else ''}{category.lower()}",
                    underline="none",
                    class_name="px-5 py-4 hover:bg-muted transition-colors flex flex-row justify-between gap-3 items-center text-foreground focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-ring",
                ),
                rx.box(
                    *[
                        rx.link(
                            get_display_name(c[0]),
                            href=get_component_link(
                                category=category,
                                clist=c,
                                prefix=prefix,
                            ),
                            class_name="text-sm font-book leading-6 text-muted-foreground hover:text-foreground transition-colors w-fit rounded-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring",
                        )
                        for c in get_components_for_category(
                            category, components[category]
                        )
                    ],
                    class_name="flex flex-col gap-2 px-5 pb-5",
                ),
                class_name="docs-catalog-card flex flex-col border border-border-subtle rounded-card bg-background overflow-hidden",
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
            class_name="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6",
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
                class_name="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6",
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
