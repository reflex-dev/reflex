import pandas as pd
import pytest

import nextpy as xt
from nextpy.components.datadisplay.datatable import (
    DataTable,
    serialize_dataframe,  # type: ignore
)
from nextpy.utils import types
from nextpy.utils.serializers import serialize


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
def test_validate_data_table(data_table_state: xt.Var, expected):
    """Test the str/render function.

    Args:
        data_table_state: The state fixture.
        expected: expected var name.

    """
    if not types.is_dataframe(data_table_state.data._var_type):
        data_table_component = DataTable.create(
            data=data_table_state.data, columns=data_table_state.columns
        )
    else:
        data_table_component = DataTable.create(data=data_table_state.data)

    data_table_dict = data_table_component.render()

    assert data_table_dict["props"] == [
        f"columns={{{expected}.columns}}",
        f"data={{{expected}.data}}",
    ]


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
        DataTable.create(**props)


@pytest.mark.parametrize(
    "fixture, err_msg, is_data_frame",
    [
        (
            "data_table_state2",
            "Annotation of the computed var assigned to the data field should be provided.",
            True,
        ),
        (
            "data_table_state3",
            "Annotation of the computed var assigned to the column field should be provided.",
            False,
        ),
        (
            "data_table_state4",
            "Annotation of the computed var assigned to the data field should be provided.",
            False,
        ),
    ],
)
def test_computed_var_without_annotation(fixture, request, err_msg, is_data_frame):
    """Test if value error is thrown when the computed var assigned to the data/column prop is not annotated.

    Args:
        fixture: the state.
        request: fixture request.
        err_msg: expected error message.
        is_data_frame: whether data field is a pandas dataframe.
    """
    with pytest.raises(ValueError) as err:
        if is_data_frame:
            DataTable.create(data=request.getfixturevalue(fixture).data)
        else:
            DataTable.create(
                data=request.getfixturevalue(fixture).data,
                columns=request.getfixturevalue(fixture).columns,
            )
    assert err.value.args[0] == err_msg


def test_serialize_dataframe():
    """Test if dataframe is serialized correctly."""
    df = pd.DataFrame(
        [["foo", "bar"], ["foo1", "bar1"]], columns=["column1", "column2"]
    )
    value = serialize(df)
    assert value == serialize_dataframe(df)
    assert isinstance(value, dict)
    assert list(value.keys()) == ["columns", "data"]
