from collections.abc import Mapping, Sequence

import pytest
from reflex_base.utils.imports import ImportVar
from reflex_base.vars.base import Var, VarData, computed_var, figure_out_type

from reflex.state import State


class CustomDict(dict[str, str]):
    """A custom dict with generic arguments."""


class ChildCustomDict(CustomDict):
    """A child of CustomDict."""


class GenericDict(dict):
    """A generic dict with no generic arguments."""


class ChildGenericDict(GenericDict):
    """A child of GenericDict."""


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (1, int),
        (1.0, float),
        ("a", str),
        ([1, 2, 3], Sequence[int]),
        ([1, 2.0, "a"], Sequence[int | float | str]),
        ({"a": 1, "b": 2}, Mapping[str, int]),
        ({"a": 1, 2: "b"}, Mapping[int | str, str | int]),
        (CustomDict(), CustomDict),
        (ChildCustomDict(), ChildCustomDict),
        (GenericDict({1: 1}), Mapping[int, int]),
        (ChildGenericDict({1: 1}), Mapping[int, int]),
    ],
)
def test_figure_out_type(value, expected):
    assert figure_out_type(value) == expected


def test_chained_var_operations_var_data_stays_bounded() -> None:
    """Deeply chained var operations keep merged VarData entries deduped.

    Regression: every ``@var_operation`` merges the same operand VarData via
    both ``_args`` and ``_return``, so without dedup in ``merge_imports`` the
    merged import entries doubled per nesting level (depth 18 produced ~1.57M
    entries and a multi-hundred-millisecond merge).
    """
    base = Var(
        _js_expr="a",
        _var_type=int,
        _var_data=VarData(imports={"my-lib": [ImportVar(tag="thing")]}),
    ).guess_type()

    chained = base
    for i in range(18):
        chained = chained + i

    var_data = chained._get_all_var_data()
    assert var_data is not None
    assert dict(var_data.imports)["my-lib"] == (ImportVar(tag="thing"),)


def test_computed_var_replace() -> None:
    class StateTest(State):
        @computed_var(cache=True)
        def cv(self) -> int:
            return 1

    cv = StateTest.cv
    assert cv._var_type is int

    replaced = cv._replace(_var_type=float)
    assert replaced._var_type is float
