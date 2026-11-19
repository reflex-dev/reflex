"""The route decorator and associated variables and functions."""

from __future__ import annotations

import functools
import re
import string
from collections.abc import Callable

from reflex_base import constants


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
            # The frontend compiles this to React Router's `*`, which matches the
            # route and its descendants only, so the segment separator is required.
            regex_parts.append("(/.*)?")
        else:
            regex_parts.append(re.escape("/" + part))
    # Join the regex parts and compile the regex
    regex_pattern = "".join(regex_parts)
    regex_pattern = f"^{regex_pattern}/?$"
    # React Router matches route paths case-insensitively by default, folding
    # ASCII letters only (its regex has no "u" flag).
    return re.compile(regex_pattern, re.IGNORECASE | re.ASCII)


# React Router folds the case of ASCII letters only (its regex has no "u" flag).
_ASCII_LOWER = str.maketrans(string.ascii_uppercase, string.ascii_lowercase)


def _fold_case(segment: str) -> str:
    """Lowercase the ASCII letters of a path segment, and nothing else.

    Args:
        segment: A route or path segment.

    Returns:
        The segment with its ASCII letters lowercased.
    """
    return segment.lower() if segment.isascii() else segment.translate(_ASCII_LOWER)


class _RouteNode:
    """A route trie node, reached by matching one path segment per level.

    A route ending at a node is stored as its rank, its position in the order
    ``get_router`` gives the routes; the lowest-ranked match wins.
    """

    __slots__ = ("catchall", "end", "min_rank", "optional", "single", "static")

    def __init__(self, no_rank: int):
        """Create an empty node.

        Args:
            no_rank: The rank meaning no route, above every real rank.
        """
        self.static: dict[str, _RouteNode] = {}
        # A [arg] segment matches any one segment, an empty one included.
        self.single: _RouteNode | None = None
        # A [[arg]] segment matches no segment or one non-empty segment.
        self.optional: _RouteNode | None = None
        self.end = no_rank
        # A [[...splat]] here matches every remaining segment, or none.
        self.catchall = no_rank
        # The best rank of any route through this node, to skip branches.
        self.min_rank = no_rank

    def child(self, part: str, no_rank: int) -> _RouteNode:
        """Get or create the node a route segment leads to.

        Args:
            part: The keyworded route segment.
            no_rank: The rank meaning no route.

        Returns:
            The child node.
        """
        if part == constants.RouteRegex.SINGLE_SEGMENT:
            node = self.single = self.single or _RouteNode(no_rank)
        elif part == constants.RouteRegex.DOUBLE_SEGMENT:
            node = self.optional = self.optional or _RouteNode(no_rank)
        elif (node := self.static.get(key := _fold_case(part))) is None:
            node = self.static[key] = _RouteNode(no_rank)
        return node


def _match(
    node: _RouteNode,
    segments: list[str],
    index: int,
    catchall_from: int,
    best: int,
) -> int:
    """Find the best-ranked route matching the path segments from ``index``.

    Args:
        node: The node reached by matching ``segments[:index]``.
        segments: The case-folded path segments.
        index: The first segment left to match.
        catchall_from: The first index after every segment holding a newline,
            which a catch-all, like the regex ``.`` it replaces, cannot match.
        best: The best rank found so far.

    Returns:
        The best rank found, ``best`` if nothing here beats it.
    """
    if node.min_rank >= best:
        return best
    remaining = len(segments) - index
    # A route may end with one trailing slash, which leaves an empty segment.
    if node.end < best and (remaining == 0 or (remaining == 1 and not segments[index])):
        best = node.end
    if node.catchall < best and index >= catchall_from:
        best = node.catchall
    if remaining:
        segment = segments[index]
        if (static := node.static.get(segment)) is not None:
            best = _match(static, segments, index + 1, catchall_from, best)
        if node.single is not None:
            best = _match(node.single, segments, index + 1, catchall_from, best)
        if node.optional is not None and segment:
            best = _match(node.optional, segments, index + 1, catchall_from, best)
    if node.optional is not None:
        best = _match(node.optional, segments, index, catchall_from, best)
    return best


def get_router(routes: list[str]) -> Callable[[str], str | None]:
    """Get a function that computes the route for a given path.

    Routes are ranked by ``route_specificity``, ties in the order given, and a
    path resolves to the best-ranked route it matches. Matching walks a trie of
    route segments, so its cost follows the path's length, not the number of
    routes.

    Args:
        routes: A list of routes to match against.

    Returns:
        A function that takes a path and returns the first matching route,
        or None if no match is found.

    Raises:
        ValueError: If a catch-all segment is not the last segment of a route.
    """
    keyworded_routes = {
        replace_brackets_with_keywords(route): route for route in routes
    }
    ranked_routes = sorted(
        keyworded_routes.items(),
        key=lambda item: route_specificity(item[0]),
    )
    no_rank = len(ranked_routes)
    root = _RouteNode(no_rank)
    index_rank = no_rank
    for rank, (keyworded_route, _) in enumerate(ranked_routes):
        if keyworded_route == constants.PageNames.INDEX_ROUTE:
            # The index route matches the root path only.
            index_rank = min(index_rank, rank)
            continue
        node = root
        node.min_rank = min(node.min_rank, rank)
        *parts, last = keyworded_route.split("/")
        for part in parts:
            if part == constants.RouteRegex.DOUBLE_CATCHALL_SEGMENT:
                msg = f"Catchall pattern `{constants.RouteRegex.SPLAT_CATCHALL}` must be at the end of the route."
                raise ValueError(msg)
            node = node.child(part, no_rank)
            node.min_rank = min(node.min_rank, rank)
        if last == constants.RouteRegex.DOUBLE_CATCHALL_SEGMENT:
            node.catchall = min(node.catchall, rank)
        else:
            node = node.child(last, no_rank)
            node.min_rank = min(node.min_rank, rank)
            node.end = min(node.end, rank)

    @functools.lru_cache(maxsize=4096)
    def get_route(path: str) -> str | None:
        """Get the best-ranked route matching a path.

        Memoized per path, so an event pays only for a cache lookup once its
        path has been seen.

        The path must be relative to ``frontend_path``, which is how the
        frontend reports it.

        Args:
            path: The path to match against the routes.

        Returns:
            The best-ranked matching route, or None if no route matches.
        """
        path = path.removeprefix("/").removesuffix("/")
        if path == "index":
            path = ""
        best = index_rank if not path else no_rank
        segments = path.split("/")
        catchall_from = 0
        if "\n" in path:
            catchall_from = max(i for i, s in enumerate(segments) if "\n" in s) + 1
        best = _match(root, [_fold_case(s) for s in segments], 0, catchall_from, best)
        return ranked_routes[best][1] if best < no_rank else None

    return get_route
