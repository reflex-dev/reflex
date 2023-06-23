"""Data display component tests fixtures."""
from typing import List

import pandas as pd
import pytest

import reflex as rx


@pytest.fixture
def data_table_state(request):
    """Get a data table state.

    Args:
        request: The request.

    Returns:
        The data table state class.
    """

    class DataTableState(rx.State):
        data = request.param["data"]
        columns = ["column1", "column2"]

    return DataTableState


@pytest.fixture
def data_table_state2():
    """Get a data table state.

    Returns:
        The data table state class.
    """

    class DataTableState(rx.State):
        _data = pd.DataFrame()

        @rx.var
        def data(self):
            return self._data

    return DataTableState


@pytest.fixture
def data_table_state3():
    """Get a data table state.

    Returns:
        The data table state class.
    """

    class DataTableState(rx.State):
        _data: List = []
        _columns: List = ["col1", "col2"]

        @rx.var
        def data(self) -> List:
            return self._data

        @rx.var
        def columns(self):
            return self._columns

    return DataTableState


@pytest.fixture
def data_table_state4():
    """Get a data table state.

    Returns:
        The data table state class.
    """

    class DataTableState(rx.State):
        _data: List = []
        _columns: List = ["col1", "col2"]

        @rx.var
        def data(self):
            return self._data

        @rx.var
        def columns(self) -> List:
            return self._columns

    return DataTableState
