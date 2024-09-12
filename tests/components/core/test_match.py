from typing import Dict, List, Tuple

import pytest

import reflex as rx
from reflex.components.core.match import Match
from reflex.state import BaseState
from reflex.utils.exceptions import MatchTypeError
from reflex.vars.base import Var


class MatchState(BaseState):
    """A test state."""

    value: int = 0
    num: int = 5
    string: str = "random string"


def test_match_components():
    """Test matching cases with return values as components."""
    match_case_tuples = (
        (1, rx.text("first value")),
        (2, 3, rx.text("second value")),
        ([1, 2], rx.text("third value")),
        ("random", rx.text("fourth value")),
        ({"foo": "bar"}, rx.text("fifth value")),
        (MatchState.num + 1, rx.text("sixth value")),
        rx.text("default value"),
    )
    match_comp = Match.create(MatchState.value, *match_case_tuples)
    match_dict = match_comp.render()  # type: ignore
    assert match_dict["name"] == "Fragment"

    [match_child] = match_dict["children"]

    assert match_child["name"] == "match"
    assert str(match_child["cond"]) == f"{MatchState.get_name()}.value"

    match_cases = match_child["match_cases"]
    assert len(match_cases) == 6

    assert match_cases[0][0]._js_expr == "1"
    assert match_cases[0][0]._var_type == int
    first_return_value_render = match_cases[0][1].render()
    assert first_return_value_render["name"] == "RadixThemesText"
    assert first_return_value_render["children"][0]["contents"] == '{"first value"}'

    assert match_cases[1][0]._js_expr == "2"
    assert match_cases[1][0]._var_type == int
    assert match_cases[1][1]._js_expr == "3"
    assert match_cases[1][1]._var_type == int
    second_return_value_render = match_cases[1][2].render()
    assert second_return_value_render["name"] == "RadixThemesText"
    assert second_return_value_render["children"][0]["contents"] == '{"second value"}'

    assert match_cases[2][0]._js_expr == "[1, 2]"
    assert match_cases[2][0]._var_type == List[int]
    third_return_value_render = match_cases[2][1].render()
    assert third_return_value_render["name"] == "RadixThemesText"
    assert third_return_value_render["children"][0]["contents"] == '{"third value"}'

    assert match_cases[3][0]._js_expr == '"random"'
    assert match_cases[3][0]._var_type == str
    fourth_return_value_render = match_cases[3][1].render()
    assert fourth_return_value_render["name"] == "RadixThemesText"
    assert fourth_return_value_render["children"][0]["contents"] == '{"fourth value"}'

    assert match_cases[4][0]._js_expr == '({ ["foo"] : "bar" })'
    assert match_cases[4][0]._var_type == Dict[str, str]
    fifth_return_value_render = match_cases[4][1].render()
    assert fifth_return_value_render["name"] == "RadixThemesText"
    assert fifth_return_value_render["children"][0]["contents"] == '{"fifth value"}'

    assert match_cases[5][0]._js_expr == f"({MatchState.get_name()}.num + 1)"
    assert match_cases[5][0]._var_type == int
    fifth_return_value_render = match_cases[5][1].render()
    assert fifth_return_value_render["name"] == "RadixThemesText"
    assert fifth_return_value_render["children"][0]["contents"] == '{"sixth value"}'

    default = match_child["default"].render()

    assert default["name"] == "RadixThemesText"
    assert default["children"][0]["contents"] == '{"default value"}'


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
    match_comp = Match.create(MatchState.value, *cases)
    assert isinstance(match_comp, Var)
    assert str(match_comp) == expected


def test_match_on_component_without_default():
    """Test that matching cases with return values as components returns a Fragment
    as the default case if not provided.
    """
    from reflex.components.base.fragment import Fragment

    match_case_tuples = (
        (1, rx.text("first value")),
        (2, 3, rx.text("second value")),
    )

    match_comp = Match.create(MatchState.value, *match_case_tuples)
    default = match_comp.render()["children"][0]["default"]  # type: ignore

    assert isinstance(default, Fragment)


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
        Match.create(MatchState.value, *match_case_tuples)


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
        Match.create(MatchState.value, *match_case)


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
        Match.create(MatchState.value, *match_case)


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
            'Match cases should have the same return types. Case 3 with return value `"red"` of type '
            "<class 'reflex.vars.sequence.LiteralStringVar'> is not <class 'reflex.components.component.BaseComponent'>",
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
            'Match cases should have the same return types. Case 3 with return value `<RadixThemesText as={"p"}> {"first value"} </RadixThemesText>` '
            "of type <class 'reflex.components.radix.themes.typography.text.Text'> is not <class 'reflex.vars.base.Var'>",
        ),
    ],
)
def test_match_different_return_types(cases: Tuple, error_msg: str):
    """Test that an error is thrown when the return values are of different types.

    Args:
        cases: The match cases.
        error_msg: Expected error message.
    """
    with pytest.raises(MatchTypeError, match=error_msg):
        Match.create(MatchState.value, *cases)


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
        Match.create(MatchState.value, *match_case)


def test_match_no_cond():
    with pytest.raises(ValueError):
        _ = Match.create(None)
