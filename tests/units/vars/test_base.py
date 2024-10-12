from typing import Dict, List, Union

import pytest

from reflex.vars.base import figure_out_type


class CustomDict(dict[str, str]):
    """A custom dict with generic arguments."""

    pass


class ChildCustomDict(CustomDict):
    """A child of CustomDict."""

    pass


class GenericDict(dict):
    """A generic dict with no generic arguments."""

    pass


class ChildGenericDict(GenericDict):
    """A child of GenericDict."""

    pass


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (1, int),
        (1.0, float),
        ("a", str),
        ([1, 2, 3], List[int]),
        ([1, 2.0, "a"], List[Union[int, float, str]]),
        ({"a": 1, "b": 2}, Dict[str, int]),
        ({"a": 1, 2: "b"}, Dict[Union[int, str], Union[str, int]]),
        (CustomDict(), CustomDict),
        (ChildCustomDict(), ChildCustomDict),
        (GenericDict({1: 1}), Dict[int, int]),
        (ChildGenericDict({1: 1}), Dict[int, int]),
    ],
)
def test_figure_out_type(value, expected):
    assert figure_out_type(value) == expected
