import pytest
import reflex as rx
from reflex.state import BaseState
from reflex.components.layout.match import Match

class MatchState(BaseState):
    value: int = 0
    num : int = 5


def test_match_components():
    match_case_tuples = (
                   (1, rx.text("first value")),
                   (2, 3, rx.text("second value")),
                   ([1,2], rx.text("third value")),
                   ("random", rx.text("fourth value")),
                   ({"foo":"bar"}, rx.text("fifth value")),
                    (MatchState.num + 1, rx.text("sixth value")),
                   rx.text("default value")
           )
    match_comp = Match.create(MatchState.value, *match_case_tuples)
    match_dict = match_comp.render()
    assert match_dict["name"] == "Fragment"

    [match_child] = match_dict["children"]

    assert match_child["name"] == "match"
    assert str(match_child["cond"]) == "{match_state.value}"

    match_cases = match_child["match_cases"]
    assert len(match_cases) == 6

    assert match_cases[0][0]._var_name == "1"
    assert match_cases[0][0]._var_type == int
    first_return_value_render = match_cases[0][1].render()
    assert first_return_value_render["name"] == "Text"
    assert first_return_value_render["children"][0]["contents"] == "{`first value`}"

    assert match_cases[1][0]._var_name == "2"
    assert match_cases[1][0]._var_type == int
    assert match_cases[1][1]._var_name == "3"
    assert match_cases[1][1]._var_type == int
    second_return_value_render = match_cases[1][2].render()
    assert second_return_value_render["name"] == "Text"
    assert second_return_value_render["children"][0]["contents"] == "{`second value`}"

    assert match_cases[2][0]._var_name == "[1, 2]"
    assert match_cases[2][0]._var_type == list
    third_return_value_render = match_cases[2][1].render()
    assert third_return_value_render["name"] == "Text"
    assert third_return_value_render["children"][0]["contents"] == "{`third value`}"

    assert match_cases[3][0]._var_name == "random"
    assert match_cases[3][0]._var_type == str
    fourth_return_value_render = match_cases[3][1].render()
    assert fourth_return_value_render["name"] == "Text"
    assert fourth_return_value_render["children"][0]["contents"] == "{`fourth value`}"

    assert match_cases[4][0]._var_name == '{"foo": "bar"}'
    assert match_cases[4][0]._var_type == dict
    fifth_return_value_render = match_cases[4][1].render()
    assert fifth_return_value_render["name"] == "Text"
    assert fifth_return_value_render["children"][0]["contents"] == "{`fifth value`}"

    assert match_cases[5][0]._var_name == '(match_state.num + 1)'
    assert match_cases[5][0]._var_type == int
    fifth_return_value_render = match_cases[5][1].render()
    assert fifth_return_value_render["name"] == "Text"
    assert fifth_return_value_render["children"][0]["contents"] == "{`sixth value`}"

    default = match_child["default"].render()

    assert default["name"] == "Text"
    assert default["children"][0]["contents"] == "{`default value`}"


def test_match_vars():
    match_case_tuples = (
        (1, rx.text("first value")),
        (2, 3, rx.text("second value")),
        ([1, 2], rx.text("third value")),
        ("random", rx.text("fourth value")),
        ({"foo": "bar"}, rx.text("fifth value")),
        (MatchState.num + 1, rx.text("sixth value")),
        rx.text("default value")
    )
    match_comp = Match.create(MatchState.value, *match_case_tuples)


def test_match_on_component_without_default():
    match_case_tuples = (
        (1, rx.text("first value")),
        (2, 3, rx.text("second value")),
    )

    match_comp = Match.create(MatchState.value, *match_case_tuples)
    default = match_comp.render()["children"][0]["default"]

    assert isinstance(default, rx.Fragment)

def test_match_on_var_no_default():
    # should throw error
    match_case_tuples = (
        (1, "red"),
        (2, 3, "blue"),
        ([1, 2], "green"),
    )

    with pytest.raises(ValueError):
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

        )
    ]
)
def test_match_default_not_last_arg(match_case):

    with pytest.raises(ValueError):
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

        )
    ]
)
def test_match_case_tuple_elements(match_case):
    with pytest.raises(ValueError):
        Match.create(MatchState.value, *match_case)

def test_match_different_return_types():
    match_case_tuples = (
        (1, rx.text("first value")),
        (2, 3, rx.text("second value")),
        ([1, 2], rx.text("third value")),
        ("random", "red"),
        ({"foo": "bar"}, "green"),
        (MatchState.num + 1, "black"),
        rx.text("default value")
    )
    with pytest.raises(TypeError):
        match_comp = Match.create(MatchState.value, *match_case_tuples)


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

        )
    ]
)
def test_match_multiple_default_cases(match_case):
    with pytest.raises(ValueError):
        Match.create(MatchState.value, *match_case)