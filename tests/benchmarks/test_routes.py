"""Benchmarks for route construction and hot-path matching."""

import re

import pytest
from pytest_codspeed import BenchmarkFixture
from reflex_base import constants

from reflex.route import get_route_args, get_router


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


@pytest.mark.parametrize("count", [10, 100, 1000])
def test_route_matching(count: int, benchmark: BenchmarkFixture):
    """Benchmark repeated matching through representative route tables.

    Args:
        count: Number of routes.
        benchmark: The CodSpeed benchmark fixture.
    """
    router = get_router(_routes(count))
    paths = ["/", "/posts/reflex", f"/section-{count - 4}/item-{count - 4}"]

    def match_paths() -> tuple[str | None, ...]:
        """Match the fixed path set.

        Returns:
            Matched route templates.
        """
        return tuple(router(path) for path in paths)

    result = benchmark(match_paths)
    assert result == ("index", "posts/[slug]", paths[-1].removeprefix("/"))


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


def test_route_argument_extraction(benchmark: BenchmarkFixture):
    """Benchmark parsing dynamic and catch-all route arguments.

    Args:
        benchmark: The CodSpeed benchmark fixture.
    """
    route = "/org/[org_id]/project/[project_id]/files/[[...splat]]"
    result = benchmark(lambda: get_route_args(route))
    assert result == {
        "org_id": constants.RouteArgType.SINGLE,
        "project_id": constants.RouteArgType.SINGLE,
        "splat": constants.RouteArgType.LIST,
    }
