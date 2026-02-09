import pandas as pd
import pytest

from reflex.components.gridjs import DataTable
from reflex.state import State
from reflex.vars.base import LiteralVar, Var


class TableState(State):
    """TableState used by tests."""

    df: pd.DataFrame = pd.DataFrame({"A": [1], "B": [2]})
    data: list[list[int]] = [[1, 2]]
    columns: list[str] = ["A", "B"]


def test_dataframe_python_columns_normalized():
    """DataFrame passed as a Python value should produce normalized LiteralVar columns."""
    df = pd.DataFrame({"A": [1], "B": [2]})

    table = DataTable.create(data=df)
    table._render()

    columns = table.columns  # type: ignore[attr-defined]

    assert isinstance(columns, LiteralVar)
    assert columns._var_value == [
        {"id": "A", "name": "A"},
        {"id": "B", "name": "B"},
    ]


def test_dataframe_var_columns_preserved():
    """DataFrame coming from State is a runtime value.
    Columns must remain a Var (frontend expression),
    not be eagerly converted to LiteralVar.
    """
    table = DataTable.create(data=TableState.df)
    table._render()

    columns = table.columns  # type: ignore[attr-defined]

    assert isinstance(columns, Var)
    assert not isinstance(columns, LiteralVar)


def test_list_columns_python_normalized():
    """Python list of column names should be normalized eagerly."""
    table = DataTable.create(
        data=[[1, 2]],
        columns=["A", "B"],
    )
    table._render()

    columns = table.columns  # type: ignore[attr-defined]

    assert isinstance(columns, LiteralVar)
    assert columns._var_value == [
        {"id": "A", "name": "A"},
        {"id": "B", "name": "B"},
    ]


def test_list_columns_var_preserved():
    """Columns coming from State must remain a Var so they
    can be transformed on the frontend.
    """
    table = DataTable.create(
        data=TableState.data,
        columns=TableState.columns,
    )
    table._render()

    columns = table.columns  # type: ignore[attr-defined]

    assert isinstance(columns, Var)
    assert not isinstance(columns, LiteralVar)


def test_dataframe_with_columns_raises():
    """DataFrame already defines columns.
    Passing explicit columns is ambiguous and must error.
    """
    df = pd.DataFrame({"A": [1]})

    with pytest.raises(ValueError):
        DataTable.create(
            data=df,
            columns=["A"],
        )
