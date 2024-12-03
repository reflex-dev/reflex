"""Shared conftest for all benchmark tests."""

from typing import Tuple

import pandas as pd
import pytest

from reflex.state import State
from reflex.testing import AppHarness, AppHarnessProd


@pytest.fixture(
    scope="session", params=[AppHarness, AppHarnessProd], ids=["dev", "prod"]
)
def app_harness_env(request):
    """Parametrize the AppHarness class to use for the test, either dev or prod.

    Args:
        request: The pytest fixture request object.

    Returns:
        The AppHarness class to use for the test.
    """
    return request.param


@pytest.fixture(params=[(10, "SmallState"), (2000, "BigState")], ids=["small", "big"])
def big_state_size(request: pytest.FixtureRequest) -> int:
    """The size of the DataFrame.

    Args:
        request: The pytest fixture request object.

    Returns:
        The size of the BigState
    """
    return request.param


@pytest.fixture
def big_state(big_state_size: Tuple[int, str]) -> State:
    """A big state with a dictionary and a list of DataFrames.

    Args:
        big_state_size: The size of the big state.

    Returns:
        A big state instance.
    """
    size, _ = big_state_size

    class BigState(State):
        """A big state."""

        d: dict[str, int]
        d_repeated: dict[str, int]
        df: list[pd.DataFrame]

    d = {str(i): i for i in range(size)}
    d_repeated = {str(i): i for i in range(size)}
    df = [pd.DataFrame({"a": [i]}) for i in range(size)]

    state = BigState(d=d, df=df, d_repeated=d_repeated)
    return state
