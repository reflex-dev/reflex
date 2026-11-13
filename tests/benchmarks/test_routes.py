"""Benchmarks for route construction and matching."""

import re

import pytest
from pytest_codspeed import BenchmarkFixture

from reflex.route import get_router

# Each kind of lookup in _lookups is repeated this many times per measured call.
LOOKUP_ROUNDS = 20


def _routes(count: int) -> list[str]:
    """Build representative static and dynamic routes.

    Args:
        count: Approximate route count.

    Returns:
        Route templates.
    """
    routes = ["index", "posts/[slug]", "files/[[...splat]]"]
    routes.extend(f"section-{index}/item-{index}" for index in range(count - 3))
    return routes


def _lookups(count: int) -> list[tuple[str, str | None]]:
    """Build paths to match against ``_routes(count)`` with the route each matches.

    Every round looks up the index, a dynamic route, the catch-all, a static
    route and a path no route matches. The static routes are spread evenly over
    the table, and every path but the index differs from round to round.

    Args:
        count: Route count passed to ``_routes``.

    Returns:
        Pairs of path and expected route template.
    """
    lookups = []
    for index in range(LOOKUP_ROUNDS):
        static = index * (count - 3) // LOOKUP_ROUNDS
        lookups.extend((
            ("/", "index"),
            (f"/posts/post-{index}", "posts/[slug]"),
            (f"/files/{index}/readme.md", "files/[[...splat]]"),
            (f"/section-{static}/item-{static}", f"section-{static}/item-{static}"),
            (f"/missing-{index}", None),
        ))
    return lookups


@pytest.mark.parametrize("count", [10, 100, 1000])
def test_route_matching(count: int, benchmark: BenchmarkFixture):
    """Benchmark matching paths through representative route tables.

    The router memoizes each path, and CodSpeed calls the benchmark once before
    measuring it, so calling the router would measure only cache hits. Calling
    the function it wraps measures the scan over the route table, which is what
    grows with the table.

    Args:
        count: Number of routes.
        benchmark: The CodSpeed benchmark fixture.
    """
    match = get_router(_routes(count)).__wrapped__  # pyright: ignore [reportFunctionMemberAccess]
    lookups = _lookups(count)
    paths = [path for path, _ in lookups]

    def match_paths() -> list[str | None]:
        """Match every path.

        Returns:
            Matched route templates.
        """
        return [match(path) for path in paths]

    assert benchmark(match_paths) == [route for _, route in lookups]


@pytest.mark.parametrize("count", [10, 100, 1000])
def test_route_table_construction(count: int, benchmark: BenchmarkFixture):
    """Benchmark cold regex construction and route ordering.

    ``re.purge()`` runs in per-round setup so every measured round compiles
    the route patterns instead of hitting the ``re`` module's pattern cache.

    Args:
        count: Number of routes.
        benchmark: The CodSpeed benchmark fixture.
    """
    routes = _routes(count)

    def purge_regex_cache():
        """Clear the ``re`` module cache so each round compiles cold."""
        re.purge()

    router = benchmark.pedantic(lambda: get_router(routes), setup=purge_regex_cache)
    assert router("/posts/reflex") == "posts/[slug]"
