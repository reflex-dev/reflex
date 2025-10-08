"""The page decorator and associated variables and functions."""

from __future__ import annotations

import sys
from collections import defaultdict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Any

    from reflex.event import EventType

DECORATED_PAGES: dict[str, list] = defaultdict(list)


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
    from reflex.config import get_config

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


class PageNamespace:
    """A namespace for page names."""

    DECORATED_PAGES = DECORATED_PAGES

    def __new__(
        cls,
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
        return page(
            route=route,
            title=title,
            image=image,
            description=description,
            meta=meta,
            script_tags=script_tags,
            on_load=on_load,
        )

    page = staticmethod(page)
    __file__ = __file__


page_namespace = PageNamespace
sys.modules[__name__] = page_namespace  # pyright: ignore[reportArgumentType]
