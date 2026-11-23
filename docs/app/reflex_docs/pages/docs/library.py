import reflex as rx
from reflex.utils.format import to_snake_case

from reflex_docs.docgen_pipeline import render_markdown
from reflex_docs.templates.docpage import docpage, h1_comp, h2_comp, text_comp_2
from reflex_docs.utils.library import get_display_name

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
                        class_name="m-0 font-heading text-lg font-normal leading-6 tracking-[-0.02em]",
                    ),
                    rx.icon(
                        "chevron-right",
                        aria_hidden=True,
                        class_name="size-3.5 shrink-0 text-muted-foreground",
                    ),
                    href=f"/library/{prefix.strip('/') + '/' if prefix.strip('/') else ''}{category.lower()}/",
                    class_name="group flex min-h-10 w-fit items-center gap-2 self-start text-foreground no-underline transition-colors hover:text-muted-foreground motion-reduce:transition-none focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ring",
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
                                class_name="inline-flex min-h-10 items-center text-sm font-normal leading-6 text-muted-foreground no-underline transition-colors hover:text-foreground motion-reduce:transition-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring",
                            ),
                        )
                        for c in get_components_for_category(
                            category, components[category]
                        )
                    ],
                    class_name="m-0 grid w-full min-w-0 max-w-[48rem] list-none grid-cols-1 gap-x-4 gap-y-1 p-0 sm:grid-cols-2 xl:grid-cols-3",
                ),
                class_name="grid min-w-0 grid-cols-1 gap-3 border-b border-border-subtle py-6 md:grid-cols-[12rem_minmax(0,1fr)] md:gap-6",
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


LIBRARY_FAQ = """## How Reflex components compare

Like Streamlit widgets, Reflex components are written in Python, but Reflex gives you full control over layout and styling. Instead of rerunning the whole script on each interaction as Streamlit does, Reflex runs event handlers that update state, and only the parts of the UI that depend on that state re-render. NiceGUI and Gradio also build web UIs in Python. Reflex's library covers forms, layouts, overlays, data tables, a spreadsheet-style data editor, and charts, with enterprise AG Grid and AG Charts components for data-heavy apps.

## Frequently asked questions

### Can I use Reflex components without learning React?

Yes. Reflex components compile to React on the frontend, but you write everything in Python. You never touch JavaScript, JSX, or React hooks.

### Do Reflex components work with pandas DataFrames?

Yes. [`rx.data_table`](/docs/library/tables-and-data-grids/data-table/) takes a pandas DataFrame directly, with built-in search, sorting, and pagination. For editable grids, use [`rx.data_editor`](/docs/library/tables-and-data-grids/data-editor/) or the enterprise [AG Grid](/docs/enterprise/ag-grid/) component.

### Can I style Reflex components with custom CSS?

Yes. Every component accepts style props and a `class_name` prop. With the [Tailwind plugin](/docs/styling/tailwind/) enabled, you can pass Tailwind utility classes to `class_name`. For animations, keyframes, or other global styles, add [custom stylesheets](/docs/styling/custom-stylesheets/).

### Are Reflex components accessible?

Many core components are built on Radix UI primitives, which follow WAI-ARIA patterns and include keyboard navigation, focus management, and screen reader support.

### Can I wrap my own React components?

Yes. Reflex can wrap any React component from npm: declare its props and events in Python and Reflex generates the bindings. See the [wrapping React guide](/docs/wrapping-react/overview/).

### Do I need to install components separately?

No. All core components are included when you install Reflex. For enterprise components like AG Grid and AG Charts, install the `reflex-enterprise` package.
"""


@docpage(
    set_path="/library/",
    right_sidebar=True,
    pseudo_right_bar=True,
    page_title="Python UI Component Library · Reflex Docs",
)
def library():
    return rx.box(
        h1_comp(
            text="Component Library",
        ),
        text_comp_2(
            text="Reflex provides 100+ UI components that work entirely in Python — no HTML, CSS, or JavaScript required. Build forms, tables, data grids, charts, and complete web interfaces using familiar Python syntax. Each component is fully documented with examples and integrates directly with your Python state.",
        ),
        component_grid(),
        rx.el.div(render_markdown(LIBRARY_FAQ), class_name="mt-8"),
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
        class_name="docs-library-index flex min-w-0 flex-col h-full mb-12",
    )
