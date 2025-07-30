from collections.abc import Mapping, Sequence

import pytest

from reflex.state import State
from reflex.vars.base import computed_var, figure_out_type


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


def test_computed_var_replace() -> None:
    class StateTest(State):
        @computed_var(cache=True)
        def cv(self) -> int:
            return 1

    cv = StateTest.cv
    assert cv._var_type is int

    replaced = cv._replace(_var_type=float)
    assert replaced._var_type is float
