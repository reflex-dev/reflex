import re

from reflex_ui_shared.route import Route

from ..state import SideBarItem


def create_item(route: Route, children=None):
    """Create a sidebar item from a route."""
    if children is None:
        name = route.title
        url = route.path
        # For "Overview", we want to keep the qualifier prefix ("Components overview")
        alt_name_for_next_prev = name if name.endswith("Overview") else ""
        # Capitalize acronyms
        acronyms = {"Api": "API", "Cli": "CLI", "Ide": "IDE", "Mcp": "MCP", "Ai": "AI"}
        name = re.sub(
            r"\b(" + "|".join(acronyms.keys()) + r")\b",
            lambda m: acronyms[m.group(0)],
            name,
        )
        return SideBarItem(
            names=name, alt_name_for_next_prev=alt_name_for_next_prev, link=url
        )
    return SideBarItem(
        names=route,
        children=list(map(create_item, children)),
    )
