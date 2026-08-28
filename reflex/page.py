"""The page decorator and associated variables and functions."""

from __future__ import annotations

import sys
from collections import defaultdict
from typing import TYPE_CHECKING

from reflex_base.config import get_config
from reflex_base.registry import RegistrationContext
from reflex_base.utils import console

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Any

    from reflex_base.event import EventType

    DECORATED_PAGES: defaultdict[str, list[tuple[Callable, dict[str, Any]]]]


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
        kwargs: dict[str, Any] = {}
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

        RegistrationContext.ensure_context().decorated_pages.append((render_fn, kwargs))

        return render_fn

    return decorator


class PageNamespaceMeta(type):
    """Metaclass serving deprecated module-level globals on the page namespace."""

    def __getattr__(cls, name: str) -> Any:
        """Provide the module-level globals that moved onto `RegistrationContext`.

        Kept so 0.9.8-era code doing `from reflex.page import DECORATED_PAGES`
        keeps working (the namespace class replaces this module in `sys.modules`,
        so a plain module `__getattr__` would never be consulted).

        Args:
            name: The name of the attribute to look up.

        Returns:
            The relocated value, resolved against the active `RegistrationContext`.

        Raises:
            AttributeError: If the attribute is not a relocated global.
        """
        if name == "DECORATED_PAGES":
            console.deprecate(
                feature_name="reflex.page.DECORATED_PAGES",
                reason=(
                    "Decorated pages now live on the active RegistrationContext. "
                    "Use RegistrationContext.ensure_context().decorated_pages to "
                    "read the list of (render_fn, kwargs) entries"
                ),
                deprecation_version="0.9.9",
                removal_version="1.0",
            )
            pages: defaultdict[str, list[tuple[Callable, dict[str, Any]]]] = (
                defaultdict(list)
            )
            pages[get_config().app_name] = (
                RegistrationContext.ensure_context().decorated_pages
            )
            return pages
        msg = f"module {cls.__module__!r} has no attribute {name!r}"
        raise AttributeError(msg)


class PageNamespace(metaclass=PageNamespaceMeta):
    """A namespace for page names."""

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
