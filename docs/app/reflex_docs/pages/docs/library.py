import reflex as rx
from reflex.utils.format import to_snake_case, to_title_case
from reflex_site_shared.components.icons import get_icon

from reflex_docs.templates.docpage import docpage, h1_comp, text_comp_2


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
                    rx.el.h1(
                        to_title_case(to_snake_case(category), sep=" "),
                        class_name="font-large text-slate-12",
                    ),
                    get_icon("new_tab", class_name="text-slate-11 [&>svg]:size-4"),
                    href=f"/library/{prefix.strip('/') + '/' if prefix.strip('/') else ''}{category.lower()}",
                    underline="none",
                    class_name="px-4 py-2 bg-slate-1 hover:bg-slate-3 transition-bg flex flex-row justify-between items-center !text-slate-12",
                ),
                rx.box(
                    *[
                        rx.link(
                            to_title_case(to_snake_case(c[0]), sep=" "),
                            href=get_component_link(
                                category=category,
                                clist=c,
                                prefix=prefix,
                            ),
                            class_name="font-small text-slate-11 hover:!text-violet-9 transition-color w-fit",
                        )
                        for c in components[category]
                    ],
                    class_name="flex flex-col gap-2.5 px-4 py-2 border-t border-slate-5",
                ),
                class_name="flex flex-col border border-slate-5 rounded-xl bg-slate-2 shadow-large overflow-hidden",
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
            h1_comp(
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
