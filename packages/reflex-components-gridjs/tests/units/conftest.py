"""Data display component tests fixtures."""

import pandas as pd
import pytest

import reflex as rx
from reflex.state import BaseState


@pytest.fixture
def data_table_state(request):
    """Get a data table state.

    Args:
        request: The request.

    Returns:
        The data table state class.
    """

    class DataTableState(BaseState):
        data = request.param["data"]
        columns = ["column1", "column2"]

    return DataTableState


@pytest.fixture
def data_table_state2():
    """Get a data table state.

    Returns:
        The data table state class.
    """

    class DataTableState(BaseState):
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

    class DataTableState(BaseState):
        _data: list = []
        _columns: list = ["col1", "col2"]

        @rx.var
        def data(self) -> list:
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

    class DataTableState(BaseState):
        _data: list = []
        _columns: list[str] = ["col1", "col2"]

        @rx.var
        def data(self):
            return self._data

        @rx.var
        def columns(self) -> list:
            return self._columns

    return DataTableState
