from reflex_site_shared.route import Route

from reflex_docs.utils.acronyms import uppercase_acronyms

from ..state import SideBarItem


def create_item(route: Route, children=None):
    """Create a sidebar item from a route."""
    if children is None:
        name = route.title
        url = route.path
        # For "Overview", we want to keep the qualifier prefix ("Components overview")
        alt_name_for_next_prev = name if name.endswith("Overview") else ""
        return SideBarItem(
            names=uppercase_acronyms(name),
            alt_name_for_next_prev=alt_name_for_next_prev,
            link=url,
        )
    return SideBarItem(
        names=route,
        children=list(map(create_item, children)),
    )
