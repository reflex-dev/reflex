"""Integration tests for all routes in Reflex."""

import sys
from collections import Counter
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parent.parent))


@pytest.fixture
def routes_fixture():
    from reflex_docs.pages import routes

    yield routes


def test_unique_routes(routes_fixture):
    assert routes_fixture is not None

    paths = [route.path for route in routes_fixture if route.path]

    # Count occurrences of each path
    path_counts = Counter(paths)
    # Find duplicate paths
    duplicates = {path: count for path, count in path_counts.items() if count > 1}

    # Assert that there are no duplicates
    assert len(duplicates) == 0, f"Duplicate routes found: {duplicates}"

    print(f"Test passed. All {len(paths)} routes are unique.")
