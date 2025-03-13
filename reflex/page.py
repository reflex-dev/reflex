"""The page decorator and associated variables and functions."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Callable, List

from reflex.config import get_config
from reflex.event import EventType

DECORATED_PAGES: dict[str, List] = defaultdict(list)


def page(
    route: str | None = None,
    title: str | None = None,
    image: str | None = None,
    description: str | None = None,
    meta: list[Any] | None = None,
    script_tags: list[Any] | None = None,
    on_load: EventType[()] | None = None,
):
    """Decorate a function as a page.

    rx.App() will automatically call add_page() for any method decorated with page
    when App.compile is called.

    All defaults are None because they will use the one from add_page().

    Note: the decorated functions still need to be imported.

    Args:
        route: The route to reach the page.
        title: The title of the page.
        image: The favicon of the page.
        description: The description of the page.
        meta: Additional meta to add to the page.
        on_load: The event handler(s) called when the page load.
        script_tags: scripts to attach to the page

    Returns:
        The decorated function.
    """

    def decorator(render_fn: Callable):
        kwargs = {}
        if route:
            kwargs["route"] = route
        if title:
            kwargs["title"] = title
        if image:
            kwargs["image"] = image
        if description:
            kwargs["description"] = description
        if meta:
            kwargs["meta"] = meta
        if script_tags:
            kwargs["script_tags"] = script_tags
        if on_load:
            kwargs["on_load"] = on_load

        DECORATED_PAGES[get_config().app_name].append((render_fn, kwargs))

        return render_fn

    return decorator


def get_decorated_pages(omit_implicit_routes: bool = True) -> list[dict[str, Any]]:
    """Get the decorated pages.

    Args:
        omit_implicit_routes: Whether to omit pages where the route will be implicitly guessed later.

    Returns:
        The decorated pages.
    """
    return sorted(
        [
            page_data
            for _, page_data in DECORATED_PAGES[get_config().app_name]
            if not omit_implicit_routes or "route" in page_data
        ],
        key=lambda x: x.get("route", ""),
    )
