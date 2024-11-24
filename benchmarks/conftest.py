"""Shared conftest for all benchmark tests."""

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


@pytest.fixture(params=[100000])
def dict_size(request: pytest.FixtureRequest) -> int:
    """The size of the dictionary.

    Args:
        request: The pytest fixture request object.

    Returns:
        The size of the dictionary.
    """
    return request.param


@pytest.fixture(params=[100000])
def df_size(request: pytest.FixtureRequest) -> int:
    """The size of the DataFrame.

    Args:
        request: The pytest fixture request object.

    Returns:
        The size of the DataFrame.
    """
    return request.param


@pytest.fixture
def big_state(
    dict_size: int,
    df_size: int,
) -> State:
    """A big state with a dictionary and a list of DataFrames.

    Args:
        dict_size: The size of the dictionary.
        df_size: The size of the DataFrame.

    Returns:
        A big state instance.
    """

    class BigState(State):
        """A big state."""

        d: dict[str, int]
        df: list[pd.DataFrame]

    d = {str(i): i for i in range(dict_size)}
    df = [pd.DataFrame({"a": [i]}) for i in range(df_size)]

    state = BigState(d=d, df=df)
    return state
