"""The page decorator and associated variables and functions."""

from reflex.components.component import Component
from reflex.event import EventHandler

DECORATED_PAGES: list

def page(
    route: str | None = None,
    title: str | None = None,
    image: str | None = None,
    description: str | None = None,
    meta: str | None = None,
    script_tags: list[Component] | None = None,
    on_load: EventHandler | list[EventHandler] | None = None,
): ...
def get_decorated_pages() -> list[dict]: ...
