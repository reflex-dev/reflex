import re
from typing import overload

from reflex_site_shared.route import Route

from ..state import SideBarItem


@overload
def create_item(route: Route, children: None = None) -> SideBarItem: ...
@overload
def create_item(route: str, children: list[Route]) -> SideBarItem: ...
def create_item(route: Route | str, children: list[Route] | None = None) -> SideBarItem:
    """Create a sidebar item from a route, or a parent item with children."""
    if isinstance(route, Route):
        # Sidebar routes always set ``title`` to a plain string at construction
        # time; the ``Route.title: str | Var | None`` field permits reactive
        # titles in the general framework but they are never used here.
        name = route.title if isinstance(route.title, str) else ""
        url = route.path
        # For "Overview", we want to keep the qualifier prefix ("Components overview")
        alt_name_for_next_prev = name if name.endswith("Overview") else ""
        # Capitalize acronyms
        acronyms = {
            "Api": "API",
            "Cli": "CLI",
            "Ide": "IDE",
            "Mcp": "MCP",
            "Ai": "AI",
            "Gcp": "GCP",
        }
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
        children=list(map(create_item, children or [])),
    )
