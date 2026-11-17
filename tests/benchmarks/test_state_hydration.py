"""Track complete snapshots of small and large state trees.

A snapshot resolves every substate's full name through the per-class metadata
caches (name and parent) on its way to serializing it, so a regression in those
caches shows up here too. A separate benchmark that only re-read the cached
metadata was dropped: with no serialization work to dilute them, CPython's
attribute-cache and specialization costs dominated, and those move several
percent with whatever ran earlier in the process.
"""

import pytest
from pytest_codspeed import BenchmarkFixture

from reflex.state import BaseState


@pytest.fixture(scope="module", params=[20, 200])
def hydration_state(request: pytest.FixtureRequest) -> BaseState:
    """Create a state tree with the requested number of substates.

    Args:
        request: The parametrized fixture request.

    Returns:
        A populated state tree.
    """
    count = request.param
    root = type(f"HydrationRoot{count}", (BaseState,), {"__module__": __name__})
    for index in range(count):
        type(
            f"HydrationChild{count}_{index}",
            (root,),
            {
                "__module__": __name__,
                "__annotations__": {"count": int, "label": str},
                "count": index,
                "label": f"sub-{index}",
            },
        )
    return root()


def test_hydration_snapshot(
    hydration_state: BaseState, benchmark: BenchmarkFixture
) -> None:
    """Measure complete snapshots of small and large state trees.

    Args:
        hydration_state: The state tree to snapshot.
        benchmark: The benchmark fixture.
    """
    benchmark(hydration_state.dict)
