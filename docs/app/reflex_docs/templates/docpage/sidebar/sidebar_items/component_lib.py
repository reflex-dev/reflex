import reflex as rx
from reflex.utils.format import to_snake_case, to_title_case

from ..state import SideBarItem


def get_display_name(name: str) -> str:
    normalized = to_snake_case(name)
    if normalized == "html":
        return "HTML"
    if normalized == "svg":
        return "SVG"
    return to_title_case(normalized, sep=" ")


def is_html_category(category: str) -> bool:
    return to_snake_case(category.replace("-", " ")) == "html"


HTML_COMPONENT_ORDER = {
    "html": 0,
    "text": 1,
    "layout": 2,
    "forms": 3,
    "media": 4,
    "tables": 5,
    "svg": 6,
}


def sort_html_components(components: list) -> list:
    return sorted(
        components,
        key=lambda component: HTML_COMPONENT_ORDER.get(
            to_snake_case(component[0]), len(HTML_COMPONENT_ORDER)
        ),
    )


def get_component_link(category, clist, prefix="") -> str:
    component_name = rx.utils.format.to_kebab_case(clist[0])
    # construct the component link. The component name points to the name of the md file.
    return f"/library/{prefix.strip('/') + '/' if prefix.strip('/') else ''}{category.lower().replace(' ', '-')}/{component_name.lower()}"


def get_category_children(category, category_list, prefix=""):
    category = category.replace("-", " ")
    if isinstance(category_list, dict):
        return SideBarItem(
            names=get_display_name(category),
            children=[
                get_category_children(c, category_list[c]) for c in category_list
            ],
        )
    category_item_children = []
    category_item_children.append(
        SideBarItem(
            names="Overview",
            link=f"/library/{prefix or ''}{category.lower().replace(' ', '-')}/",
        )
    )
    for c in category_list:
        item = SideBarItem(
            names=get_display_name(c[0]),
            link=get_component_link(category, c, prefix=prefix),
        )
        category_item_children.append(item)
    return SideBarItem(
        names=get_display_name(category), children=category_item_children
    )


def get_sidebar_items_component_lib():
    from reflex_docs.pages.docs import component_list

    library_item_children = []

    for category in component_list:
        if is_html_category(category):
            continue
        category_item = get_category_children(category, component_list[category])
        library_item_children.append(category_item)

    return [
        *library_item_children,
    ]


def get_sidebar_items_html():
    from reflex_docs.pages.docs import component_list

    html_children = [
        SideBarItem(names="Overview", link="/library/html/"),
    ]
    html_children.extend([
        SideBarItem(
            names=get_display_name(component[0]),
            link=get_component_link("Html", component),
        )
        for component in sort_html_components(component_list.get("Html", []))
    ])
    return [SideBarItem(names="HTML", children=html_children)]


def get_sidebar_items_graphings():
    from reflex_docs.pages.docs import graphing_components

    graphing_children = []
    for category in graphing_components:
        category_item = get_category_children(
            category, graphing_components[category], prefix="graphing/"
        )
        graphing_children.append(category_item)

    return [*graphing_children]


component_lib = get_sidebar_items_component_lib()
html_lib = get_sidebar_items_html()
graphing_libs = get_sidebar_items_graphings()
