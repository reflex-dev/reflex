import reflex as rx
from pandas import DataFrame
import pandas as pd
import numpy as np
import re
import contextlib
from typing import Any, Dict, List, Sequence, Tuple, cast, Union

from reflex.components.component import Component


def get_fqn(the_type: type) -> str:
    """Get module.type_name for a given type."""
    return f"{the_type.__module__}.{the_type.__qualname__}"


def get_fqn_type(obj: object) -> str:
    """Get module.type_name for a given object."""
    return get_fqn(type(obj))


def is_type(obj: object, fqn_type_pattern: Union[str, re.Pattern[str]]) -> bool:
    """Check type without importing expensive modules.

    Parameters
    ----------
    obj : object
        The object to type-check.
    fqn_type_pattern : str or regex
        The fully-qualified type string or a regular expression.
        Regexes should start with `^` and end with `$`.

    Example
    -------

    To check whether something is a Matplotlib Figure without importing
    matplotlib, use:

    >>> is_type(foo, 'matplotlib.figure.Figure')

    """
    fqn_type = get_fqn_type(obj)
    if isinstance(fqn_type_pattern, str):
        return fqn_type_pattern == fqn_type
    else:
        return fqn_type_pattern.match(fqn_type) is not None


def convert_anything_to_df(
        data: Any,
        ensure_copy: bool = False,
    ) -> DataFrame:

    """Try to convert different formats to a Pandas Dataframe.

    Parameters
    ----------
    data : ndarray, Iterable, dict, DataFrame, Styler, pa.Table, None, dict, list, or any

    ensure_copy: bool
        If True, make sure to always return a copy of the data. If False, it depends on the
        type of the data. For example, a Pandas DataFrame will be returned as-is.


    Returns
    -------
    pandas.DataFrame

    """
    if is_type(data,"pandas.core.frame.DataFrame"):
        return data.copy() if ensure_copy else cast(DataFrame, data)


    if is_type(data, "numpy.ndarray"):
        if len(data.shape) == 0:
            return DataFrame([])
        return DataFrame(data)

    # Try to convert to pandas.DataFrame. This will raise an error is df is not
    # compatible with the pandas.DataFrame constructor.
    try:
        return DataFrame(data)

    except ValueError:
        if isinstance(data, dict):
            with contextlib.suppress(ValueError):
                # Try to use index orient as back-up to support key-value dicts
                return DataFrame.from_dict(data, orient="index")
        raise TypeError(f"Unable to convert object of type `{type(data)}` to `pandas.DataFrame`.")
        


def _parse_x_column(df: pd.DataFrame, x_from_user: str | None) -> str | None:
    if x_from_user is None:
        return None

    elif isinstance(x_from_user, str):
        if x_from_user not in df.columns:
            raise ValueError(f"{x_from_user} not in columns in data.")

        return x_from_user

    else:
        raise TypeError(
            f"x parameter should be a column name (str) or None to use the dataframe's index. Value given: {x_from_user}, (type {type(x_from_user)})"
        )


def is_sequence(seq: Any) -> bool:
    """True if input looks like a sequence."""
    if isinstance(seq, str):
        return False
    try:
        len(seq)
    except Exception:
        return False
    return True


def _parse_y_columns(
    df: pd.DataFrame,
    y_from_user: str | Sequence[str] | None,
    x_column: str | None,
) -> List[str]:
    y_column_list: List[str] = []

    if y_from_user is None:
        y_column_list = list(df.columns)

    elif isinstance(y_from_user, str):
        y_column_list = [y_from_user]

    # this allows y to take in a list of columns, come back to this
    elif is_sequence(y_from_user):
        y_column_list = list(str(col) for col in y_from_user)

    else:
        raise TypeError(
            f"y parameter should be a column name (str) or list thereof. Value given: {y_from_user} (type {type(y_from_user)})"
        )

    for col in y_column_list:
        if col not in df.columns:
            raise ValueError(f"{col} not in columns in data.")

    # y_column_list should only include x_column when user explicitly asked for it.
    if x_column in y_column_list and (not y_from_user or x_column not in y_from_user):
        y_column_list.remove(x_column)

    return y_column_list


def _maybe_reset_index_in_place(
    df: pd.DataFrame, x_column: str | None, y_column_list: List[str]
) -> str | None:
    if x_column is None and len(y_column_list) > 0:
        if df.index.name is None:
            # Pick column name that is unlikely to collide with user-given names.
            x_column = "index--p5bJXXpQgv"
        else:
            # Reuse index's name for the new column.
            x_column = df.index.name

        df.index.name = x_column
        df.reset_index(inplace=True)

    return x_column


def _drop_unused_columns(df: pd.DataFrame, *column_names: str | None) -> pd.DataFrame:
    """Returns a subset of df, selecting only column_names that aren't None."""

    # We can't just call set(col_names) because sets don't have stable ordering,
    # which means tests that depend on ordering will fail.
    # Performance-wise, it's not a problem, though, since this function is only ever
    # used on very small lists.
    seen = set()
    keep = []

    for x in column_names:
        if x is None:
            continue
        if x in seen:
            continue
        seen.add(x)
        keep.append(x)

    return df[keep]


def _convert_col_names_to_str_in_place(
    df: pd.DataFrame,
    x_column: str | None,
    y_column_list: List[str],
) -> Tuple[str | None, List[str], str | None, str | None]:
    """Converts column names to strings"""
    column_names = list(df.columns)  # list() converts RangeIndex, etc, to regular list.
    str_column_names = [str(c) for c in column_names]
    df.columns = pd.Index(str_column_names)

    return (
        None if x_column is None else str(x_column),
        [str(c) for c in y_column_list],
    )


def _melt_data(
    df: pd.DataFrame,
    columns_to_leave_alone: List[str],
    columns_to_melt: List[str] | None,
    new_y_column_name: str,
) -> pd.DataFrame:
    """Converts a wide-format dataframe to a long-format dataframe."""

    melted_df = pd.melt(
        df,
        id_vars=columns_to_leave_alone,
        value_vars=columns_to_melt,
        value_name=new_y_column_name,
    )

    # # An extra check if the melted column contains too many values with mixed types.
    # # This currently breaks some of our inputs, so must consider if we want to use it or not.
    #y_series = melted_df[new_y_column_name]

    # if (
    #     y_series.dtype == "object"
    #     and "mixed" in infer_dtype(y_series)
    #     and len(y_series.unique()) > 100
    # ):
    #     raise ValueError(
    #         "The columns used for rendering the chart contain too many values with mixed types. Please select the columns manually via the y parameter."
    #     )

    #return fixed_df
    return melted_df


def _maybe_melt(
    df: pd.DataFrame,
    x_column: str | None,
    y_column_list: List[str],
) -> Tuple[pd.DataFrame, str | None, str | None]:
    """If multiple columns are set for y, melt the dataframe into long format."""
    y_column: str | None

    if len(y_column_list) == 0:
        y_column = None

    y_column = "value--p5bJXXpQgv"

    columns_to_leave_alone = [x_column]

    df = _melt_data(
        df=df,
        columns_to_leave_alone=columns_to_leave_alone,
        columns_to_melt=y_column_list,
        new_y_column_name=y_column,
    )

    return df, y_column


def prep_data(
    df: pd.DataFrame,
    x_column: str | None,
    y_column_list: List[str],
) -> Tuple[pd.DataFrame, str | None, str | None, str | None, str | None]:
    """Prepares the data for charting. This is also used in add_rows.

    Returns the prepared dataframe and the new names of the x column (taking the index reset into
    consideration) and y, color, and size columns.
    """

    # If y is provided, but x is not, we'll use the index as x.
    # So we need to pull the index into its own column.
    x_column = _maybe_reset_index_in_place(df, x_column, y_column_list)

    # Drop columns we're not using.
    selected_data = _drop_unused_columns(df, x_column, *y_column_list)

    # Make sure all columns have string names.
    x_column, y_column_list = _convert_col_names_to_str_in_place(selected_data, x_column, y_column_list)

    # Maybe melt data from wide format into long format.
    melted_data, y_column = _maybe_melt(selected_data, x_column, y_column_list)

    # Return the data, but also the new names to use for x, y, and color.
    return melted_data, x_column, y_column


def prepare_y_and_color(y, color):
    
    # Set default color if color is None
    default_color = "#8884d8"
    if color is None:
        color = [default_color] * len(y)

    if isinstance(y, str):
        y = [y]

    if isinstance(color, str):
        color = [color]

    # If both are lists and have the same length, zip them together
    if isinstance(y, list) and isinstance(color, list) and len(y) == len(color):
        return zip(y, color)

    # If lists are of different lengths, raise an error
    else:
        raise ValueError("y and color must be of the same length")
    


def bar_chart_high_api(
        data: pd.DataFrame | np.ndarray | Dict[str, List[str | int]] | List[Dict[str, Any]], 
        x: str | None, 
        y: str | List[str], 
        color: str | List[str] = None, 
        legend: bool = True,
        tooltip: bool = True,
        cartesian_axis: bool = True,
        x_axis_brush: bool = True,
        **props,
        ) -> Component:
    
    """Create a bar chart.

    Args:
        data: The data to plot.
        x: The column name to use for the x-axis. If None, the dataframe's index will be used.
        y: The column name to use for the y-axis / y-axes.
        color: The color to use for each of the bars created. If None, the default color will be used.
        legend: Whether to display the legend.
        tooltip: Whether to display the tooltip.
        cartesian_axis: Whether to display the cartesian axis.
        x_axis_brush: Whether to display the x-axis brush.
    """

    df = convert_anything_to_df(data)

    x_column = _parse_x_column(df, x)

    y_column_list = _parse_y_columns(df, y, x_column)

    df, x_column, y_column = prep_data(df, x_column, y_column_list)

    pivot_df = df.pivot(index=x, columns='variable', values='value--p5bJXXpQgv').reset_index()
    
    list_of_dicts = pivot_df.to_dict(orient='records')

    y_and_color = prepare_y_and_color(y, color)

    # must write a test here to make sure that list_of_dicts is of type List[Dict[str, Any]]

    return rx.recharts.bar_chart(
        rx.cond(
            tooltip,
            rx.recharts.graphing_tooltip(),
        ),
        
        *[rx.recharts.bar(data_key=key[0], stroke=key[1], fill=key[1])
        for key in y_and_color
        ],
        rx.recharts.x_axis(data_key=x),
        rx.recharts.y_axis(),

        rx.cond(
            legend,
            rx.recharts.legend(),
        ),

        

        rx.cond(
            cartesian_axis,
            rx.recharts.cartesian_grid(stroke_dasharray="3 3"),
        ),

        rx.cond(
            x_axis_brush,
            rx.recharts.brush(height=30, stroke="#8884d8"),
        ),

        data=list_of_dicts,
        **props,
    )


