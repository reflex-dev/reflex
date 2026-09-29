from ..state import SideBarItem
from .item import create_item


def get_sidebar_items_changelog():
    from reflex_docs.pages.docs import changelog_packages

    return [
        SideBarItem(names=package, link=route)
        for package, route in changelog_packages.items()
    ]


def get_sidebar_items_api_reference():
    from reflex_docs.pages.docs import api_reference, apiref

    pages = {route.path: route for route in vars(api_reference).values()}
    routes = [pages.pop(f"/api-reference/{slug}/") for slug in apiref.section_order]
    # A page added under docs/api-reference/ without a place in section_order
    # lands at the end rather than dropping out of the sidebar.
    routes += pages.values()
    return [create_item(route) for route in routes]


api_reference = get_sidebar_items_api_reference()
changelog_items = get_sidebar_items_changelog()
