import pynecone as pc

import pytest


@pytest.fixture
def data_table_state(request):
    class DataTableState(pc.State):
        data = request.param["data"]
        columns = ["column1", "column2"]

    return DataTableState
