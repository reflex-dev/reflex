import re
from typing import Tuple

import pytest

import reflex as rx
from reflex.components.core.match import match
from reflex.state import BaseState
from reflex.utils.exceptions import MatchTypeError
from reflex.vars.base import Var


class MatchState(BaseState):
    """A test state."""

    value: int = 0
    num: int = 5
    string: str = "random string"


@pytest.mark.parametrize(
    "cases, expected",
    [
        (
            (
                (1, "first"),
                (2, 3, "second value"),
                ([1, 2], "third-value"),
                ("random", "fourth_value"),
                ({"foo": "bar"}, "fifth value"),
                (MatchState.num + 1, "sixth value"),
                (f"{MatchState.value} - string", MatchState.string),
                (MatchState.string, f"{MatchState.value} - string"),
                "default value",
            ),
            f'(() => {{ switch (JSON.stringify({MatchState.get_name()}.value)) {{case JSON.stringify(1):  return ("first");  break;case JSON.stringify(2): case JSON.stringify(3):  return '
            '("second value");  break;case JSON.stringify([1, 2]):  return ("third-value");  break;case JSON.stringify("random"):  '
            'return ("fourth_value");  break;case JSON.stringify(({ ["foo"] : "bar" })):  return ("fifth value");  '
            f'break;case JSON.stringify(({MatchState.get_name()}.num + 1)):  return ("sixth value");  break;case JSON.stringify(({MatchState.get_name()}.value+" - string")):  '
            f'return ({MatchState.get_name()}.string);  break;case JSON.stringify({MatchState.get_name()}.string):  return (({MatchState.get_name()}.value+" - string"));  break;default:  '
            'return ("default value");  break;};})()',
        ),
        (
            (
                (1, "first"),
                (2, 3, "second value"),
                ([1, 2], "third-value"),
                ("random", "fourth_value"),
                ({"foo": "bar"}, "fifth value"),
                (MatchState.num + 1, "sixth value"),
                (f"{MatchState.value} - string", MatchState.string),
                (MatchState.string, f"{MatchState.value} - string"),
                MatchState.string,
            ),
            f'(() => {{ switch (JSON.stringify({MatchState.get_name()}.value)) {{case JSON.stringify(1):  return ("first");  break;case JSON.stringify(2): case JSON.stringify(3):  return '
            '("second value");  break;case JSON.stringify([1, 2]):  return ("third-value");  break;case JSON.stringify("random"):  '
            'return ("fourth_value");  break;case JSON.stringify(({ ["foo"] : "bar" })):  return ("fifth value");  '
            f'break;case JSON.stringify(({MatchState.get_name()}.num + 1)):  return ("sixth value");  break;case JSON.stringify(({MatchState.get_name()}.value+" - string")):  '
            f'return ({MatchState.get_name()}.string);  break;case JSON.stringify({MatchState.get_name()}.string):  return (({MatchState.get_name()}.value+" - string"));  break;default:  '
            f"return ({MatchState.get_name()}.string);  break;}};}})()",
        ),
    ],
)
def test_match_vars(cases, expected):
    """Test matching cases with return values as Vars.

    Args:
        cases: The match cases.
        expected: The expected var full name.
    """
    match_comp = match(MatchState.value, *cases)  # pyright: ignore[reportCallIssue]
    assert isinstance(match_comp, Var)
    assert str(match_comp) == expected


def test_match_on_component_without_default():
    """Test that matching cases with return values as components returns a Fragment
    as the default case if not provided.
    """
    match_case_tuples = (
        (1, rx.text("first value")),
        (2, 3, rx.text("second value")),
    )

    match_comp = match(MatchState.value, *match_case_tuples)

    assert isinstance(match_comp, Var)


def test_match_on_var_no_default():
    """Test that an error is thrown when cases with return Values as Var do not have a default case."""
    match_case_tuples = (
        (1, "red"),
        (2, 3, "blue"),
        ([1, 2], "green"),
    )

    with pytest.raises(
        ValueError,
        match="For cases with return types as Vars, a default case must be provided",
    ):
        match(MatchState.value, *match_case_tuples)


@pytest.mark.parametrize(
    "match_case",
    [
        (
            (1, "red"),
            (2, 3, "blue"),
            "black",
            ([1, 2], "green"),
        ),
        (
            (1, rx.text("first value")),
            (2, 3, rx.text("second value")),
            ([1, 2], rx.text("third value")),
            rx.text("default value"),
            ("random", rx.text("fourth value")),
            ({"foo": "bar"}, rx.text("fifth value")),
            (MatchState.num + 1, rx.text("sixth value")),
        ),
    ],
)
def test_match_default_not_last_arg(match_case):
    """Test that an error is thrown when the default case is not the last arg.

    Args:
        match_case: The cases to match.
    """
    with pytest.raises(
        ValueError,
        match="rx.match should have tuples of cases and a default case as the last argument.",
    ):
        match(MatchState.value, *match_case)  # pyright: ignore[reportCallIssue]


@pytest.mark.parametrize(
    "match_case",
    [
        (
            (1, "red"),
            (2, 3, "blue"),
            ("green",),
            "black",
        ),
        (
            (1, rx.text("first value")),
            (2, 3, rx.text("second value")),
            ([1, 2],),
            rx.text("default value"),
        ),
    ],
)
def test_match_case_tuple_elements(match_case):
    """Test that a match has at least 2 elements(a condition and a return value).

    Args:
        match_case: The cases to match.
    """
    with pytest.raises(
        ValueError,
        match="A case tuple should have at least a match case element and a return value.",
    ):
        match(MatchState.value, *match_case)  # pyright: ignore[reportCallIssue]


@pytest.mark.parametrize(
    "cases, error_msg",
    [
        (
            (
                (1, rx.text("first value")),
                (2, 3, rx.text("second value")),
                ([1, 2], rx.text("third value")),
                ("random", "red"),
                ({"foo": "bar"}, "green"),
                (MatchState.num + 1, "black"),
                rx.text("default value"),
            ),
            "Match cases should have the same return types. Expected return types to be of type Component or Var[Component]. Return type of case 3 is <class 'str'>. Return type of case 4 is <class 'str'>. Return type of case 5 is <class 'str'>",
        ),
        (
            (
                ("random", "red"),
                ({"foo": "bar"}, "green"),
                (MatchState.num + 1, "black"),
                (1, rx.text("first value")),
                (2, 3, rx.text("second value")),
                ([1, 2], rx.text("third value")),
                rx.text("default value"),
            ),
            "Match cases should have the same return types. Expected return types to be of type Component or Var[Component]. Return type of case 0 is <class 'str'>. Return type of case 1 is <class 'str'>. Return type of case 2 is <class 'str'>",
        ),
    ],
)
def test_match_different_return_types(cases: Tuple, error_msg: str):
    """Test that an error is thrown when the return values are of different types.

    Args:
        cases: The match cases.
        error_msg: Expected error message.
    """
    with pytest.raises(MatchTypeError, match=re.escape(error_msg)):
        match(MatchState.value, *cases)  # pyright: ignore[reportCallIssue]


@pytest.mark.parametrize(
    "match_case",
    [
        (
            (1, "red"),
            (2, 3, "blue"),
            ([1, 2], "green"),
            "black",
            "white",
        ),
        (
            (1, rx.text("first value")),
            (2, 3, rx.text("second value")),
            ([1, 2], rx.text("third value")),
            ("random", rx.text("fourth value")),
            ({"foo": "bar"}, rx.text("fifth value")),
            (MatchState.num + 1, rx.text("sixth value")),
            rx.text("default value"),
            rx.text("another default value"),
        ),
    ],
)
def test_match_multiple_default_cases(match_case):
    """Test that there is only one default case.

    Args:
        match_case: the cases to match.
    """
    with pytest.raises(ValueError, match="rx.match can only have one default case."):
        match(MatchState.value, *match_case)  # pyright: ignore[reportCallIssue]


def test_match_no_cond():
    with pytest.raises(ValueError):
        _ = match(None)  # pyright: ignore[reportCallIssue]
