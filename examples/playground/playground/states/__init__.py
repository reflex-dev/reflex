"""The states behind the playground's demo pages, one module per area."""


def route_arg(path: str) -> str:
    """Read the last segment of a route, the argument of a dynamic page.

    Args:
        path: The page's path, e.g. ``/data/product/42``.

    Returns:
        The last segment, e.g. ``42``.
    """
    return path.rstrip("/").rsplit("/", 1)[-1]
