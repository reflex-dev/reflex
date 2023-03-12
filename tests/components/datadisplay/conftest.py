"""Data display component tests fixtures."""

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
