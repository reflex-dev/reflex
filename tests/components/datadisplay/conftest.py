"""Data display component tests fixtures."""

import pytest

import pynecone as pc


@pytest.fixture
def data_table_state(request):
    """Get a data table state."""

    class DataTableState(pc.State):
        data = request.param["data"]
        columns = ["column1", "column2"]

    return DataTableState
