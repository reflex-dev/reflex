"""Track state-tree hydration costs below and above the metadata LRU capacity."""

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


def test_hydration_metadata(
    hydration_state: BaseState, benchmark: BenchmarkFixture
) -> None:
    """Measure repeated metadata walks without state serialization costs.

    Args:
        hydration_state: The populated tree whose classes to visit.
        benchmark: The benchmark fixture.
    """
    classes = [
        type(hydration_state),
        *(type(s) for s in hydration_state.substates.values()),
    ]

    @benchmark
    def walk() -> None:
        """Visit the metadata used to fetch and reconnect a state tree."""
        for cls in classes:
            cls.get_name()
            cls.get_full_name()
            cls.get_parent_state()
            cls.get_root_state()
