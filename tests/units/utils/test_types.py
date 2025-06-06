from typing import Any, Literal

import pytest

from reflex.utils import types
from reflex.vars.base import Var


@pytest.mark.parametrize(
    ("params", "allowed_value_str", "value_str"),
    [
        (["size", 1, Literal["1", "2", "3"], "Heading"], "'1','2','3'", "1"),
        (["size", "1", Literal[1, 2, 3], "Heading"], "1,2,3", "'1'"),
    ],
)
def test_validate_literal_error_msg(params, allowed_value_str, value_str):
    with pytest.raises(ValueError) as err:
        types.validate_literal(*params)

    assert (
        err.value.args[0] == f"prop value for {params[0]!s} of the `{params[-1]}` "
        f"component should be one of the following: {allowed_value_str}. Got {value_str} instead"
    )


@pytest.mark.parametrize(
    ("cls", "cls_check", "expected"),
    [
        (int, Any, True),
        (tuple[int], Any, True),
        (list[int], Any, True),
        (int, int, True),
        (int, object, True),
        (int, int | str, True),
        (int, str | int, True),
        (str, str | int, True),
        (str, int | str, True),
        (int, str | float | int, True),
        (int, str | float, False),
        (int, float | str, False),
        (int, str, False),
        (int, list[int], False),
    ],
)
def test_issubclass(
    cls: types.GenericType, cls_check: types.GenericType, expected: bool
) -> None:
    assert types._issubclass(cls, cls_check) == expected


class CustomDict(dict[str, str]):
    """A custom dict with generic arguments."""


class ChildCustomDict(CustomDict):
    """A child of CustomDict."""


class GenericDict(dict):
    """A generic dict with no generic arguments."""


class ChildGenericDict(GenericDict):
    """A child of GenericDict."""


@pytest.mark.parametrize(
    ("cls", "expected"),
    [
        (int, False),
        (str, False),
        (float, False),
        (tuple[int], True),
        (list[int], True),
        (int | str, True),
        (str | int, True),
        (dict[str, int], True),
        (CustomDict, True),
        (ChildCustomDict, True),
        (GenericDict, False),
        (ChildGenericDict, False),
    ],
)
def test_has_args(cls, expected: bool) -> None:
    assert types.has_args(cls) == expected


@pytest.mark.parametrize(
    ("value", "cls", "expected"),
    [
        (1, int, True),
        (1, str, False),
        (1, float, True),
        ("1", str, True),
        ("1", int, False),
        (1.0, float, True),
        (1.0, int, False),
        ([], list[int], True),
        ([1], list[int], True),
        ([1.0], list[int], False),
        ([1], list[str], False),
        ({}, dict[str, str], True),
        ({"a": "b"}, dict[str, str], True),
        ({"a": 1}, dict[str, str], False),
        (False, bool, True),
        (False, Var[bool], True),
        (False, Var[bool] | None, True),
        (Var.create(False), bool, True),
        (Var.create(False), Var[bool], True),
        (Var.create(False), Var[bool] | None, True),
        (Var.create(False), Var[bool] | str, True),
    ],
)
def test_isinstance(value, cls, expected: bool) -> None:
    assert types._isinstance(value, cls, nested=1, treat_var_as_type=True) == expected
