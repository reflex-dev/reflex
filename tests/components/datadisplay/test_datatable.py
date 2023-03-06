import os

import pytest
import pandas as pd

import pynecone as pc
from pynecone.components import data_table


@pytest.mark.parametrize(
    "data_table_state",
    [
        pytest.param({"data": ["foo", "bar"]}),
        pytest.param({"data": [["foo", "bar"], ["foo1", "bar1"]]}),
        pytest.param({"data": pd.DataFrame([["foo", "bar"], ["foo1", "bar1"]], columns=["column1", "column2"])}),
    ],
    indirect=True,
)
def test_validate_data_table(data_table_state: pc.Var):
    data_table_component = data_table(data=data_table_state.data, columns=data_table_state.columns)

    assert str(
        data_table_component) == f"<DataTableGrid columns={{data_table_state.columns}}{os.linesep}data={{" \
                                 f"data_table_state.data}}/> "


@pytest.mark.parametrize(
    "props",
    [
        {"data": [["foo", "bar"], ["foo1", "bar1"]]},
        {"data": pd.DataFrame([["foo", "bar"], ["foo1", "bar1"]]), "columns": ["column1", "column2"]},
    ],
)
def test_invalid_props(props):
    with pytest.raises(ValueError):
        data_table(**props)
