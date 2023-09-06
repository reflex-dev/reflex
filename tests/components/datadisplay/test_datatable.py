import pandas as pd
import pytest

import reflex as rx
from reflex.components import data_table
from reflex.utils import types


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
def test_validate_data_table(data_table_state: rx.Var, expected):
    """Test the str/render function.

    Args:
        data_table_state: The state fixture.
        expected: expected var name.

    """
    props = {"data": data_table_state.data}
    if not types.is_dataframe(data_table_state.data.type_):
        props["columns"] = data_table_state.columns
    data_table_component = data_table(**props)  # type: ignore

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
        data_table(**props)


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
            data_table(data=request.getfixturevalue(fixture).data)
        else:
            data_table(
                data=request.getfixturevalue(fixture).data,
                columns=request.getfixturevalue(fixture).columns,
            )
    assert err.value.args[0] == err_msg
