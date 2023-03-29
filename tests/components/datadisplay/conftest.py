"""Data display component tests fixtures."""

import pandas as pd
import pytest

import pynecone as pc


@pytest.fixture
def data_table_state(request):
    """Get a data table state.

    Args:
        request: The request.

    Returns:
        The data table state class.
    """

    class DataTableState(pc.State):
        data = request.param["data"]
        columns = ["column1", "column2"]

    return DataTableState


@pytest.fixture
def data_table_state2():
    """Get a data table state.

    Returns:
        The data table state class.
    """

    class DataTableState(pc.State):
        _data = pd.DataFrame()

        @pc.var  # type: ignore
        def data(self):
            return self._data

    return DataTableState
