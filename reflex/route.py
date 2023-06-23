"""The route decorator and associated variables and functions."""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Union

from reflex import constants
from reflex.event import EventHandler

DECORATED_ROUTES = []


def route(
    route: Optional[str] = None,
    title: Optional[str] = None,
    image: Optional[str] = None,
    description: Optional[str] = None,
    on_load: Optional[Union[EventHandler, List[EventHandler]]] = None,
):
    """Decorate a function as a page.

    rx.App() will automatically call add_page() for any method decorated with route
    when App.compile is called.

    All defaults are None because they will use the one from add_page().

    Note: the decorated functions still need to be imported.

    Args:
        route: The route to reach the page.
        title: The title of the page.
        image: The favicon of the page.
        description: The description of the page
        on_load: The event handler(s) called when the page load.

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


def verify_route_validity(route: str) -> None:
    """Verify if the route is valid, and throw an error if not.

    Args:
        route: The route that need to be checked

    Raises:
        ValueError: If the route is invalid.
    """
    pattern = catchall_in_route(route)
    if pattern and not route.endswith(pattern):
        raise ValueError(f"Catch-all must be the last part of the URL: {route}")


def get_route_args(route: str) -> Dict[str, str]:
    """Get the dynamic arguments for the given route.

    Args:
        route: The route to get the arguments for.

    Returns:
        The route arguments.
    """
    args = {}

    def add_route_arg(match: re.Match[str], type_: str):
        """Add arg from regex search result.

        Args:
            match: Result of a regex search
            type_: The assigned type for this arg

        Raises:
            ValueError: If the route is invalid.
        """
        arg_name = match.groups()[0]
        if arg_name in args:
            raise ValueError(
                f"Arg name [{arg_name}] is used more than once in this URL"
            )
        args[arg_name] = type_

    # Regex to check for route args.
    check = constants.RouteRegex.ARG
    check_strict_catchall = constants.RouteRegex.STRICT_CATCHALL
    check_opt_catchall = constants.RouteRegex.OPT_CATCHALL

    # Iterate over the route parts and check for route args.
    for part in route.split("/"):
        match_opt = check_opt_catchall.match(part)
        if match_opt:
            add_route_arg(match_opt, constants.RouteArgType.LIST)
            break

        match_strict = check_strict_catchall.match(part)
        if match_strict:
            add_route_arg(match_strict, constants.RouteArgType.LIST)
            break

        match = check.match(part)
        if match:
            # Add the route arg to the list.
            add_route_arg(match, constants.RouteArgType.SINGLE)
    return args


def catchall_in_route(route: str) -> str:
    """Extract the catchall part from a route.

    Args:
        route: the route from which to extract

    Returns:
        str: the catchall part of the URI
    """
    match_ = constants.RouteRegex.CATCHALL.search(route)
    return match_.group() if match_ else ""


def catchall_prefix(route: str) -> str:
    """Extract the prefix part from a route that contains a catchall.

    Args:
        route: the route from which to extract

    Returns:
        str: the prefix part of the URI
    """
    pattern = catchall_in_route(route)
    return route.replace(pattern, "") if pattern else ""
