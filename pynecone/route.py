"""The route decorator and associated variables."""

from typing import Optional

from pynecone.event import EventHandler

DECORATED_ROUTES = []


def route(
    route: Optional[str] = None,
    title: Optional[str] = None,
    image: Optional[str] = None,
    description: Optional[str] = None,
    on_load: Optional[EventHandler] = None,
):
    """Decorate a function as a page.

    pc.App() will automatically call add_page() for any method decorated with route
    when App.compile is called.

    All defaults are None because they will use the one from add_page().

    Note: the decorated functions still need to be imported.

    Args:
        route: The route to reach the page.
        title: The title of the page.
        image: The favicon of the page.
        description: The description of the page
        on_load: The event handler called when the page load.

    Returns:
        The decorated function.
    """

    def decorator(render_fn):
        kwargs = {}
        if route:
            kwargs["route"] = route
        if title:
            kwargs["title"] = title
        if image:
            kwargs["image"] = image
        if description:
            kwargs["description"] = description
        if on_load:
            kwargs["on_load"] = on_load

        DECORATED_ROUTES.append((render_fn, kwargs))

        return render_fn

    return decorator
