"""Manage routing for the application."""

import dataclasses
import inspect
from collections.abc import Callable

import reflex as rx
from reflex.event import EventType


@dataclasses.dataclass(kw_only=True)
class Route:
    """A page route."""

    # The path of the route.
    path: str

    # The page title.
    title: str | rx.Var | None = None

    # The page description.
    description: str | None = None

    # The page image.
    image: str | None = None

    # The page extra meta data.
    meta: list[dict[str, str]] | None = None

    # Background color for the page.
    background_color: str | None = None

    # The component to render for the route.
    component: Callable[[], rx.Component]

    # whether to add the route to the app's pages. This is typically used
    # to delay adding the 404 page(which is explicitly added in reflex_blog.py).
    # https://github.com/reflex-dev/reflex-web/pull/659#pullrequestreview-2021171902
    add_as_page: bool = True

    # The on_load function to call when the page is loaded.
    on_load: EventType[()] | None = None


def get_path(component_fn: Callable, route: str):
    """Get the path for a page based on the file location.

    Args:
        component_fn: The component function for the page.
        route: The route path for the page.

    Returns:
            The component.
    """
    module = inspect.getmodule(component_fn)
    if module is None:
        msg = f"Could not find module for {component_fn}"
        raise ValueError(msg)

    # Create a path based on the module name.
    return module.__name__.replace(".", "/").replace("_", "-").split(route)[1] + "/"
