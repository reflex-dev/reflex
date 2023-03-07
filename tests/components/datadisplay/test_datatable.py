import os

import pandas as pd
import pytest

import pynecone as pc
from pynecone import utils
from pynecone.components import data_table


@pytest.mark.parametrize(
    "data_table_state,expected",
    [
        pytest.param(
            {
                "data": pd.DataFrame(
                    [["foo", "bar"], ["foo1", "bar1"]], columns=["column1", "column2"]
                )
            },
            "data_table_state.data",
        ),
        pytest.param({"data": ["foo", "bar"]}, "data_table_state"),
        pytest.param({"data": [["foo", "bar"], ["foo1", "bar1"]]}, "data_table_state"),
    ],
    indirect=["data_table_state"],
)
def test_validate_data_table(data_table_state: pc.Var, expected):
    """Test the str/render function.

    Args:
        data_table_state: The state fixture.
        expected: expected var name.

    """
    props = {"data": data_table_state.data}
    if not utils.is_dataframe(data_table_state.data.type_):
        props["columns"] = data_table_state.columns
    data_table_component = data_table(**props)

    assert (
        str(data_table_component)
        == f"<DataTableGrid columns={{{expected}.columns}}{os.linesep}data={{"
        f"{expected}.data}}/>"
    )


@pytest.mark.parametrize(
    "props",
    [
        {"data": [["foo", "bar"], ["foo1", "bar1"]]},
        {
            "data": pd.DataFrame([["foo", "bar"], ["foo1", "bar1"]]),
            "columns": ["column1", "column2"],
        },
    ],
)
def test_invalid_props(props):
    """Test if value error is thrown when invalid props are passed.

    Args:
        props: props to pass in component.
    """
    with pytest.raises(ValueError):
        data_table(**props)
