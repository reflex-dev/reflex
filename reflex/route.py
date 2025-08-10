"""The route decorator and associated variables and functions."""

from __future__ import annotations

import re
from collections.abc import Callable

from reflex import constants


def verify_route_validity(route: str) -> None:
    """Verify if the route is valid, and throw an error if not.

    Args:
        route: The route that need to be checked

    Raises:
        ValueError: If the route is invalid.
    """
    route_parts = route.removeprefix("/").split("/")
    for i, part in enumerate(route_parts):
        if constants.RouteRegex.SLUG.fullmatch(part):
            continue
        if not part.startswith("[") or not part.endswith("]"):
            msg = (
                f"Route part `{part}` is not valid. Reflex only supports "
                "alphabetic characters, underscores, and hyphens in route parts. "
            )
            raise ValueError(msg)
        if part.startswith(("[[...", "[...")):
            if part != constants.RouteRegex.SPLAT_CATCHALL:
                msg = f"Catchall pattern `{part}` is not valid. Only `{constants.RouteRegex.SPLAT_CATCHALL}` is allowed."
                raise ValueError(msg)
            if i != len(route_parts) - 1:
                msg = f"Catchall pattern `{part}` must be at the end of the route."
                raise ValueError(msg)
            continue
        if part.startswith("[["):
            if constants.RouteRegex.OPTIONAL_ARG.fullmatch(part):
                continue
            msg = (
                f"Route part `{part}` with optional argument is not valid. "
                "Reflex only supports optional arguments that start with an alphabetic character or underscore, "
                "followed by alphanumeric characters or underscores."
            )
            raise ValueError(msg)
        if not constants.RouteRegex.ARG.fullmatch(part):
            msg = (
                f"Route part `{part}` with argument is not valid. "
                "Reflex only supports argument names that start with an alphabetic character or underscore, "
                "followed by alphanumeric characters or underscores."
            )
            raise ValueError(msg)


def get_route_args(route: str) -> dict[str, str]:
    """Get the dynamic arguments for the given route.

    Args:
        route: The route to get the arguments for.

    Returns:
        The route arguments.
    """
    args = {}

    def _add_route_arg(arg_name: str, type_: str):
        if arg_name in args:
            msg = (
                f"Arg name `{arg_name}` is used more than once in the route `{route}`."
            )
            raise ValueError(msg)
        args[arg_name] = type_

    # Regex to check for route args.
    argument_regex = constants.RouteRegex.ARG
    optional_argument_regex = constants.RouteRegex.OPTIONAL_ARG

    # Iterate over the route parts and check for route args.
    for part in route.split("/"):
        if part == constants.RouteRegex.SPLAT_CATCHALL:
            _add_route_arg("splat", constants.RouteArgType.LIST)
            break

        optional_argument = optional_argument_regex.match(part)
        if optional_argument:
            _add_route_arg(optional_argument.group(1), constants.RouteArgType.SINGLE)
            continue

        argument = argument_regex.match(part)
        if argument:
            _add_route_arg(argument.group(1), constants.RouteArgType.SINGLE)
            continue

    return args


def replace_brackets_with_keywords(input_string: str) -> str:
    """Replace brackets and everything inside it in a string with a keyword.

    Example:
        >>> replace_brackets_with_keywords("/posts")
        '/posts'
        >>> replace_brackets_with_keywords("/posts/[slug]")
        '/posts/__SINGLE_SEGMENT__'
        >>> replace_brackets_with_keywords("/posts/[slug]/comments")
        '/posts/__SINGLE_SEGMENT__/comments'
        >>> replace_brackets_with_keywords("/posts/[[slug]]")
        '/posts/__DOUBLE_SEGMENT__'
        >>> replace_brackets_with_keywords("/posts/[[...splat]]")
        '/posts/__DOUBLE_CATCHALL_SEGMENT__'

    Args:
        input_string: String to replace.

    Returns:
        new string containing keywords.
    """
    # Replace [<slug>] with __SINGLE_SEGMENT__
    return constants.RouteRegex.ARG.sub(
        constants.RouteRegex.SINGLE_SEGMENT,
        # Replace [[slug]] with __DOUBLE_SEGMENT__
        constants.RouteRegex.OPTIONAL_ARG.sub(
            constants.RouteRegex.DOUBLE_SEGMENT,
            # Replace [[...splat]] with __DOUBLE_CATCHALL_SEGMENT__
            input_string.replace(
                constants.RouteRegex.SPLAT_CATCHALL,
                constants.RouteRegex.DOUBLE_CATCHALL_SEGMENT,
            ),
        ),
    )


def route_specificity(keyworded_route: str) -> tuple[int, int, int]:
    """Get the specificity of a route with keywords.

    The smaller the number, the more specific the route is.

    Args:
        keyworded_route: The route with keywords.

    Returns:
        A tuple containing the counts of double catchall segments,
        double segments, and single segments in the route.
    """
    return (
        keyworded_route.count(constants.RouteRegex.DOUBLE_CATCHALL_SEGMENT),
        keyworded_route.count(constants.RouteRegex.DOUBLE_SEGMENT),
        keyworded_route.count(constants.RouteRegex.SINGLE_SEGMENT),
    )


def get_route_regex(keyworded_route: str) -> re.Pattern:
    """Get the regex pattern for a route with keywords.

    Args:
        keyworded_route: The route with keywords.

    Returns:
        A compiled regex pattern for the route.
    """
    if keyworded_route == "index":
        return re.compile(re.escape("/"))
    path_parts = keyworded_route.split("/")
    regex_parts = []
    for part in path_parts:
        if part == constants.RouteRegex.SINGLE_SEGMENT:
            # Match a single segment (/slug)
            regex_parts.append(r"/[^/]*")
        elif part == constants.RouteRegex.DOUBLE_SEGMENT:
            # Match a single optional segment (/slug or nothing)
            regex_parts.append(r"(/[^/]+)?")
        elif part == constants.RouteRegex.DOUBLE_CATCHALL_SEGMENT:
            regex_parts.append(".*")
        else:
            regex_parts.append(re.escape("/" + part))
    # Join the regex parts and compile the regex
    regex_pattern = "".join(regex_parts)
    regex_pattern = f"^{regex_pattern}/?$"
    return re.compile(regex_pattern)


def get_router(routes: list[str]) -> Callable[[str], str | None]:
    """Get a function that computes the route for a given path.

    Args:
        routes: A list of routes to match against.

    Returns:
        A function that takes a path and returns the first matching route,
        or None if no match is found.
    """
    keyworded_routes = {
        replace_brackets_with_keywords(route): route for route in routes
    }
    sorted_routes_by_specificity = sorted(
        keyworded_routes.items(),
        key=lambda item: route_specificity(item[0]),
    )
    regexed_routes = [
        (get_route_regex(keyworded_route), original_route)
        for keyworded_route, original_route in sorted_routes_by_specificity
    ]

    def get_route(path: str) -> str | None:
        """Get the first matching route for a given path.

        Args:
            path: The path to match against the routes.

        Returns:
            The first matching route, or None if no match is found.
        """
        path = "/" + path.removeprefix("/").removesuffix("/")
        if path == "/index":
            path = "/"
        for regex, original_route in regexed_routes:
            if regex.fullmatch(path):
                return original_route
        return None

    return get_route
