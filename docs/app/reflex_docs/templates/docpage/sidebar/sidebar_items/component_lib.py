import reflex as rx
from reflex.utils.format import to_snake_case, to_title_case

from ..state import SideBarItem


def get_component_link(category, clist, prefix="") -> str:
    component_name = rx.utils.format.to_kebab_case(clist[0])
    # construct the component link. The component name points to the name of the md file.
    return f"/docs/library/{prefix.strip('/') + '/' if prefix.strip('/') else ''}{category.lower().replace(' ', '-')}/{component_name.lower()}"


def get_category_children(category, category_list, prefix=""):
    category = category.replace("-", " ")
    if isinstance(category_list, dict):
        return SideBarItem(
            names=category,
            children=[
                get_category_children(c, category_list[c]) for c in category_list
            ],
        )
    category_item_children = []
    category_item_children.append(
        SideBarItem(
            names="Overview",
            link=f"/docs/library/{prefix or ''}{category.lower().replace(' ', '-')}/",
        )
    )
    for c in category_list:
        component_name = to_snake_case(c[0])
        name = to_title_case(component_name, sep=" ")
        item = SideBarItem(
            names=name,
            link=get_component_link(category, c, prefix=prefix),
        )
        category_item_children.append(item)
    return SideBarItem(names=category, children=category_item_children)


def get_sidebar_items_component_lib():
    from reflex_docs.pages.docs import component_list

    library_item_children = []

    for category in component_list:
        category_item = get_category_children(category, component_list[category])
        library_item_children.append(category_item)

    return [
        *library_item_children,
    ]


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
graphing_libs = get_sidebar_items_graphings()
