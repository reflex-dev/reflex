import reflex as rx
from reflex.utils.format import to_snake_case, to_title_case
from reflex_site_shared.constants import REFLEX_ASSETS_CDN

from reflex_docs.docgen_pipeline import render_markdown
from reflex_docs.pages.docs.metadata import truncate_meta_description
from reflex_docs.templates.docpage import docpage, h1_comp, text_comp_2


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

HTML_CARD_PREVIEWS = {
    "html": ("layout", "box"),
    "text": ("typography", "text"),
    "layout": ("layout", "grid"),
    "forms": ("forms", "input"),
    "media": ("media", "image"),
    "tables": ("tables-and-data-grids", "table"),
    "svg": ("data-display", "icon"),
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


def get_preview_asset(name: str, section: str) -> tuple[str, str]:
    if to_snake_case(section) == "html":
        return HTML_CARD_PREVIEWS.get(to_snake_case(name), ("layout", "box"))
    return section.lower(), name.lower()


def component_card(name: str, link: str, section: str) -> rx.Component:
    """Link a component preview to its reference without obscuring the artwork.

    Args:
        name: Component name used to select its preview and visible label.
        link: Canonical component reference URL.
        section: Library category containing the preview.

    Returns:
        A single focusable card with a decorative preview and readable label.
    """
    preview_section, preview_name = get_preview_asset(name, section)

    def preview_src(mode: str) -> str:
        """Resolve locally bundled previews or existing CDN artwork.

        Args:
            mode: Color mode for the preview.

        Returns:
            Image asset URL.
        """
        path = f"components_previews/{preview_section}/{mode}/{preview_name}.svg"
        if (preview_section, preview_name) == ("charts", "treemap"):
            return rx.asset(path)
        return f"{REFLEX_ASSETS_CDN}{path}"

    return rx.el.a(
        rx.el.div(
            rx.image(
                src=preview_src("light"),
                loading="lazy",
                alt="",
                style={"filter": "grayscale(1)"},
                class_name="object-contain object-center h-full w-full dark:hidden",
            ),
            rx.image(
                src=preview_src("dark"),
                loading="lazy",
                alt="",
                style={"filter": "grayscale(1)"},
                class_name="object-contain object-center h-full w-full dark:block hidden",
            ),
            aria_hidden=True,
            class_name="aspect-[320/232] w-full overflow-hidden border-b border-border-subtle bg-muted",
        ),
        rx.el.div(
            rx.el.span(
                get_display_name(name),
                class_name="min-w-0 font-heading text-lg font-normal leading-6 tracking-[-0.02em] text-foreground",
            ),
            rx.icon(
                "arrow-up-right",
                size=16,
                aria_hidden=True,
                class_name="shrink-0 text-muted-foreground",
            ),
            class_name="flex min-h-16 items-center justify-between gap-3 px-5 py-4",
        ),
        href=link,
        class_name="docs-library-card group flex min-w-0 flex-col overflow-hidden rounded-[20px] border border-border-subtle bg-background no-underline transition-colors hover:border-border-strong hover:bg-subtle motion-reduce:transition-none focus-visible:outline-2 focus-visible:-outline-offset-4 focus-visible:outline-ring",
    )


def get_component_list(component_type: str = "core"):
    from reflex_docs.pages.docs import component_list, graphing_components

    if component_type == "core":
        return component_list
    elif component_type == "graphing":
        return graphing_components
    else:
        raise ValueError(f"Unknown component type: {component_type}")


def render_component_grid(component_category: str, component_list: dict, prefix: str = "") -> rx.Component:
    """Render the component card grid for a category.

    Args:
        component_category: The category name to render cards for.
        component_list: Dict mapping category names to component lists.
        prefix: URL prefix for component links.

    Returns:
        A grid of component cards.
    """
    from reflex_docs.templates.docpage.sidebar.sidebar_items import get_component_link

    return rx.el.div(
        *[
            component_card(
                name=component[0],
                link=get_component_link(
                    component_category,
                    component,
                    prefix.strip("/") + "/" if prefix.strip("/") else "",
                ),
                section=component_category,
            )
            for component in get_components_for_category(
                component_category, component_list[component_category]
            )
        ],
        class_name="gap-5 grid min-w-0 grid-cols-1 md:grid-cols-2 xl:grid-cols-3",
    )


def create_previews(
    path: str,
    description: str,
    component_category: str,
    prefix: str = "",
    type: str = "core",
):
    meta_description = truncate_meta_description(description)

    @docpage(
        right_sidebar=False,
        set_path=f"/library{prefix.rstrip('/')}/" + path.strip("/") + "/",
        page_title=f"{get_display_name(component_category)} Component Library · Reflex Docs",
        description=meta_description,
    )
    def page() -> rx.Component:
        component_list = get_component_list(type)
        if component_category == "State":
            return rx.el.div(
                h1_comp(text="State"),
                render_markdown(
                    "Reflex state connects your components to application data. "
                    "Store values in an `rx.State` class, pass its vars to component "
                    "props, and update those values from event handlers.\n\n"
                    "## Start with state and events\n\n"
                    "- [State overview](/docs/state/overview/): define application "
                    "state and connect it to your interface.\n"
                    "- [Base vars](/docs/vars/base-vars/): store typed values that "
                    "components can display.\n"
                    "- [Computed vars](/docs/vars/computed-vars/): derive values "
                    "from existing state.\n"
                    "- [Events](/docs/events/events-overview/): update state in "
                    "response to user interactions.\n\n"
                    "## Build reusable interactive components\n\n"
                    "Use [component state](/docs/state-structure/component-state/) "
                    "when each instance needs its own data. Use "
                    "[conditional rendering](/docs/components/conditional-rendering/) "
                    "and [rendering iterables](/docs/components/rendering-iterables/) "
                    "to make your interface respond to state changes."
                ),
                class_name="docs-library flex min-w-0 flex-col w-full mb-10",
            )
        if component_category == "Tables-And-Data-Grids":
            return rx.el.div(
                h1_comp(text=get_display_name(component_category)),
                text_comp_2(
                    text=description,
                ),
                rx.el.h2(
                    "Which table component should I use?",
                    class_name="mt-8 font-heading text-2xl font-normal leading-8 tracking-[-0.02em] text-foreground",
                ),
                rx.el.ul(
                    rx.el.li(
                        rx.el.strong("rx.table", class_name="font-semibold text-foreground"),
                        " — Composable semantic table for custom layouts. Build headers, rows, and cells with full styling control. Best for small datasets or when you need complete control over the table structure.",
                        class_name="mt-3 text-sm leading-6 text-muted-foreground",
                    ),
                    rx.el.li(
                        rx.el.strong("rx.data_table", class_name="font-semibold text-foreground"),
                        " — Drop in a pandas DataFrame and enable search, sort, and pagination with `search=True`, `sort=True`, and `pagination=True`. Perfect for displaying static data from CSV files or database queries. Read-only by default.",
                        class_name="mt-3 text-sm leading-6 text-muted-foreground",
                    ),
                    rx.el.li(
                        rx.el.strong("rx.data_editor", class_name="font-semibold text-foreground"),
                        " — Spreadsheet-like editing with cell selection and inline updates. Use this when users need to edit data directly in the grid, like in an admin panel or data entry form.",
                        class_name="mt-3 text-sm leading-6 text-muted-foreground",
                    ),
                    rx.el.li(
                        rx.el.strong("AG Grid", class_name="font-semibold text-foreground"),
                        " (enterprise) — The most powerful option. Includes advanced filtering, column pivoting, row grouping, master-detail, tree data, and Excel export. See the ",
                        rx.el.a(
                            "AG Grid docs",
                            href="/docs/enterprise/ag-grid/",
                            class_name="docs-text-link underline underline-offset-4",
                        ),
                        " to get started.",
                        class_name="mt-3 text-sm leading-6 text-muted-foreground",
                    ),
                    class_name="mt-4 mb-8 list-none space-y-0 p-0",
                ),
                render_component_grid(component_category, component_list, prefix),
                class_name="docs-library flex min-w-0 flex-col h-full mb-10",
            )
        if component_category in ["Charts", "Other-Charts"]:
            return rx.el.div(
                h1_comp(text=get_display_name(component_category)),
                text_comp_2(
                    text=description,
                ),
                rx.el.h2(
                    "Choosing a charting library",
                    class_name="mt-8 font-heading text-2xl font-normal leading-8 tracking-[-0.02em] text-foreground",
                ),
                rx.el.ul(
                    rx.el.li(
                        rx.el.strong("Recharts", class_name="font-semibold text-foreground"),
                        " (built-in) — Declarative React charts with a simple API. Best for standard business charts like bar, line, area, and pie. Works great for dashboards and reports. All Recharts components are included in Reflex.",
                        class_name="mt-3 text-sm leading-6 text-muted-foreground",
                    ),
                    rx.el.li(
                        rx.el.strong("Plotly", class_name="font-semibold text-foreground"),
                        " (rx.plotly) — Interactive scientific charts with zoom, pan, and hover. Supports 3D plots, contours, and statistical charts. Use this when you need publication-quality figures or complex scientific visualizations.",
                        class_name="mt-3 text-sm leading-6 text-muted-foreground",
                    ),
                    rx.el.li(
                        rx.el.strong("Matplotlib", class_name="font-semibold text-foreground"),
                        " (pyplot) — Render any matplotlib.pyplot figure in your web app. Best when you already have matplotlib code from notebooks or scripts. Supports all matplotlib chart types but outputs static images.",
                        class_name="mt-3 text-sm leading-6 text-muted-foreground",
                    ),
                    rx.el.li(
                        rx.el.strong("AG Charts", class_name="font-semibold text-foreground"),
                        " (enterprise) — High-performance enterprise charts with smooth animations and advanced features. See the ",
                        rx.el.a(
                            "AG Charts docs",
                            href="/docs/enterprise/ag-chart/",
                            class_name="docs-text-link underline underline-offset-4",
                        ),
                        " for examples.",
                        class_name="mt-3 text-sm leading-6 text-muted-foreground",
                    ),
                    class_name="mt-4 mb-8 list-none space-y-0 p-0",
                ),
                render_component_grid(component_category, component_list, prefix),
                class_name="docs-library flex min-w-0 flex-col h-full mb-10",
            )
        return rx.el.div(
            rx.el.div(
                h1_comp(text=get_display_name(component_category)),
                text_comp_2(
                    text=description,
                ),
                class_name="flex flex-col w-full",
            ),
            render_component_grid(component_category, component_list, prefix),
            class_name="docs-library flex min-w-0 flex-col h-full mb-10",
        )

    return page


# Core Components
# Notes:
# - For the component_category, each word is capitalized and separated by a dash. Example: Data-Display
# - The path is used to match the name of the component's images folder inside "assets/components_previews/".
# - The svgs files are snake_case. Example: data_editor.svg
core_components_dict = {
    "data-display": {
        "path": "data-display",
        "description": "Tools to show information clearly. These include ways to highlight important details, show user pictures, display lists, indicate progress, and organize data neatly.",
        "component_category": "Data-Display",
    },
    "disclosure": {
        "path": "disclosure",
        "description": "Components for revealing or hiding content, such as tabs and accordions. These are useful for creating expandable sections, organizing information, and improving user interface navigation.",
        "component_category": "Disclosure",
    },
    "dynamic_rendering": {
        "path": "dynamic-rendering",
        "description": "Components that help with dynamic rendering, such as conditional rendering and dynamic components. These are useful for creating responsive and interactive user interfaces.",
        "component_category": "Dynamic-Rendering",
    },
    "forms": {
        "path": "forms",
        "description": "Components for collecting user input, such as text fields, checkboxes, and radio buttons. These are useful for creating interactive forms and user input.",
        "component_category": "Forms",
    },
    "html": {
        "path": "html",
        "description": "Low-level HTML elements exposed through the rx.el namespace. These are useful when you need native browser elements with direct styling control.",
        "component_category": "Html",
    },
    "layout": {
        "path": "layout",
        "description": "Components that help with layout, such as containers, grids, and spacing. These are useful for creating responsive and interactive user interfaces.",
        "component_category": "Layout",
    },
    "media": {
        "path": "media",
        "description": "Components that help with media, such as images, videos, and audio. These are useful for creating responsive and interactive user interfaces.",
        "component_category": "Media",
    },
    "other": {
        "path": "other",
        "description": "Miscellaneous components that don't fit into other categories, such as clipboard, script, skeleton, and theme. These components provide additional functionality and customization options for your application.",
        "component_category": "Other",
    },
    "overlays": {
        "path": "overlay",
        "description": "Components that help with overlays, such as modals, popovers, and tooltips. These are useful for creating responsive and interactive user interfaces.",
        "component_category": "Overlay",
    },
    "tables_and_data_grids": {
        "path": "tables-and-data-grids",
        "description": "Build tables and data grids in Python with Reflex. Use rx.table for simple semantic tables, rx.data_table for searchable pandas DataFrames, rx.data_editor for spreadsheet-style editing, or the enterprise AG Grid component for advanced features like filtering, pivoting, and cell selection. All in pure Python.",
        "component_category": "Tables-And-Data-Grids",
    },
    "typography": {
        "path": "typography",
        "description": "Components that help with typography, such as headings, paragraphs, and lists. These are useful for creating responsive and interactive user interfaces.",
        "component_category": "Typography",
    },
    "state": {
        "path": "state",
        "description": "Connect Reflex components to Python state, typed vars, computed values, and event handlers. Find guides for reusable interactive components and dynamic rendering.",
        "component_category": "State",
    },
}

library_previews = [
    create_previews(
        path=value["path"],
        description=value["description"],
        component_category=value["component_category"],
        type="core",
    )
    for key, value in core_components_dict.items()
]

# Graphing Components
graphing_components_dict = {
    "charts": {
        "path": "charts",
        "description": "Create interactive charts and graphs in Python with Reflex. Build bar, line, area, pie, scatter, radar, and more chart types on top of Recharts for data visualization — all in pure Python, no JavaScript.",
        "component_category": "Charts",
    },
    "general": {
        "path": "general",
        "description": "General-purpose graphing components — axes, legends, tooltips, grids, and more — for customizing your Python charts and data visualizations in Reflex. Combine them to build clear, interactive charts in pure Python.",
        "component_category": "General",
    },
    "other-charts": {
        "path": "other-charts",
        "description": "Additional Python charting options in Reflex, including Plotly and Matplotlib (pyplot). Render interactive Plotly Express figures and any Matplotlib plot in your web app — all in pure Python.",
        "component_category": "Other-Charts",
    },
}

graphing_previews = [
    create_previews(
        path=value["path"],
        description=value["description"],
        component_category=value["component_category"],
        prefix="/graphing",
        type="graphing",
    )
    for key, value in graphing_components_dict.items()
]


components_previews_pages = library_previews + graphing_previews
