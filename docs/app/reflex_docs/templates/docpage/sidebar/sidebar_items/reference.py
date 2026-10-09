from ..state import SideBarItem
from .item import create_item


def get_sidebar_items_changelog():
    from reflex_docs.pages.docs import changelog, changelog_packages

    upgrading = SideBarItem(
        names="Upgrading",
        children=[
            SideBarItem(
                names="Upgrading to 0.10",
                link=changelog.upgrading.upgrading_to_0_10.path,
            ),
        ],
    )
    return [
        upgrading,
        *(
            SideBarItem(names=package, link=route)
            for package, route in changelog_packages.items()
        ),
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
