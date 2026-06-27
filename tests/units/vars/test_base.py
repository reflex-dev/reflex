from collections.abc import Mapping, Sequence

import pytest
from reflex_base.vars.base import computed_var, figure_out_type

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


def test_computed_var_replace() -> None:
    class StateTest(State):
        @computed_var(cache=True)
        def cv(self) -> int:
            return 1

    cv = StateTest.cv
    assert cv._var_type is int

    replaced = cv._replace(_var_type=float)
    assert replaced._var_type is float


def test_reset_unique_variable_names_is_deterministic():
    """Resetting the unique-name generator reproduces the same name sequence.

    Auto-memo content hashes embed these names, so a second in-process compile
    must regenerate identical ones (the RNG state and used-name set otherwise
    persist process-wide and drift).
    """
    from reflex_base.vars.base import (
        get_unique_variable_name,
        reset_unique_variable_names,
    )

    reset_unique_variable_names()
    first = [get_unique_variable_name() for _ in range(8)]
    # Without a reset, the sequence keeps advancing (and dedups against the
    # already-used set), so it differs.
    assert [get_unique_variable_name() for _ in range(8)] != first
    # After a reset it reproduces the original sequence exactly.
    reset_unique_variable_names()
    assert [get_unique_variable_name() for _ in range(8)] == first
