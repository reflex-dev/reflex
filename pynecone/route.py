"""The route decorator and associated variables."""
from functools import wraps

DECORATED_ROUTES = []


def route(route=None, title=None, image=None, description=None, on_load=None):
    """Decorate a function as a page.

    pc.App() will automatically call add_page() for any method decorated with route
    when App.compile is called.

    Note: the decorated functions still need to be imported

    Args:
        route (_type_, optional): The route to reach the page. Defaults to None.
        title (_type_, optional): The title of the page. Defaults to None.
        image (_type_, optional): The favicon of the page. Defaults to None.
        description (_type_, optional): The description of the page. Defaults to None.
        on_load (_type_, optional): The event handler called when the page load. Defaults to None.

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
