import re
from collections.abc import Sequence

import pytest
from reflex_base.components.component import Component
from reflex_base.constants.state import FIELD_MARKER
from reflex_base.utils.exceptions import MatchTypeError
from reflex_base.utils.imports import ImportVar
from reflex_base.vars.base import Var
from reflex_components_core.core.match import Match

import reflex as rx
from reflex.state import BaseState


class MatchState(BaseState):
    """A test state."""

    value: int = 0
    num: int = 5
    string: str = "random string"
    tags: set[str] = {"c", "d"}


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
    match_comp = rx.match(MatchState.value, *match_case_tuples)

    assert isinstance(match_comp, Component)
    match_dict = match_comp.render()
    assert match_dict["name"] == "Fragment"

    [match_child] = match_dict["children"]

    assert str(match_child["cond"]) == f"{MatchState.get_name()}.value" + FIELD_MARKER

    match_cases = match_child["match_cases"]
    assert len(match_cases) == 6
    assert match_cases[0][0] == ["1"]
    first_return_value_render = match_cases[0][1]
    assert first_return_value_render["name"] == "RadixThemesText"
    assert first_return_value_render["children"][0]["contents"] == '"first value"'

    assert match_cases[1][0] == ["2", "3"]
    second_return_value_render = match_cases[1][1]
    assert second_return_value_render["name"] == "RadixThemesText"
    assert second_return_value_render["children"][0]["contents"] == '"second value"'

    assert match_cases[2][0] == ["[1, 2]"]
    third_return_value_render = match_cases[2][1]
    assert third_return_value_render["name"] == "RadixThemesText"
    assert third_return_value_render["children"][0]["contents"] == '"third value"'

    assert match_cases[3][0] == ['"random"']
    fourth_return_value_render = match_cases[3][1]
    assert fourth_return_value_render["name"] == "RadixThemesText"
    assert fourth_return_value_render["children"][0]["contents"] == '"fourth value"'

    assert match_cases[4][0] == ['({ ["foo"] : "bar" })']
    fifth_return_value_render = match_cases[4][1]
    assert fifth_return_value_render["name"] == "RadixThemesText"
    assert fifth_return_value_render["children"][0]["contents"] == '"fifth value"'

    assert match_cases[5][0] == [f"({MatchState.get_name()}.num{FIELD_MARKER} + 1)"]
    fifth_return_value_render = match_cases[5][1]
    assert fifth_return_value_render["name"] == "RadixThemesText"
    assert fifth_return_value_render["children"][0]["contents"] == '"sixth value"'

    default = match_child["default"]

    assert default["name"] == "RadixThemesText"
    assert default["children"][0]["contents"] == '"default value"'


@pytest.mark.parametrize(
    ("cases", "expected"),
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
            (
                f'(() => {{ switch (JSON.stringify({MatchState.get_name()}.value{FIELD_MARKER})) {{case JSON.stringify(1):  return ("first");  break;case JSON.stringify(2): case JSON.stringify(3):  return '
                '("second value");  break;case JSON.stringify([1, 2]):  return ("third-value");  break;case JSON.stringify("random"):  '
                'return ("fourth_value");  break;case JSON.stringify(({ ["foo"] : "bar" })):  return ("fifth value");  '
                f'break;case JSON.stringify(({MatchState.get_name()}.num{FIELD_MARKER} + 1)):  return ("sixth value");  break;case JSON.stringify(({MatchState.get_name()}.value{FIELD_MARKER}+" - string")):  '
                f'return ({MatchState.get_name()}.string{FIELD_MARKER});  break;case JSON.stringify({MatchState.get_name()}.string{FIELD_MARKER}):  return (({MatchState.get_name()}.value{FIELD_MARKER}+" - string"));  break;default:  '
                'return ("default value");  break;};})()'
            ),
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
            (
                f'(() => {{ switch (JSON.stringify({MatchState.get_name()}.value{FIELD_MARKER})) {{case JSON.stringify(1):  return ("first");  break;case JSON.stringify(2): case JSON.stringify(3):  return '
                '("second value");  break;case JSON.stringify([1, 2]):  return ("third-value");  break;case JSON.stringify("random"):  '
                'return ("fourth_value");  break;case JSON.stringify(({ ["foo"] : "bar" })):  return ("fifth value");  '
                f'break;case JSON.stringify(({MatchState.get_name()}.num{FIELD_MARKER} + 1)):  return ("sixth value");  break;case JSON.stringify(({MatchState.get_name()}.value{FIELD_MARKER}+" - string")):  '
                f'return ({MatchState.get_name()}.string{FIELD_MARKER});  break;case JSON.stringify({MatchState.get_name()}.string{FIELD_MARKER}):  return (({MatchState.get_name()}.value{FIELD_MARKER}+" - string"));  break;default:  '
                f"return ({MatchState.get_name()}.string{FIELD_MARKER});  break;}};}})()"
            ),
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


def test_match_set_cases_compare_by_elements():
    """A set subject and set cases are compared by their elements, not their order.

    A set reaches the frontend in its iteration order, which depends on the hash
    seed, so both sets are made canonical before the JSON comparison. Type tags
    keep lists distinct from a set's comparison keys, as in Python.
    """
    tags = f"{MatchState.get_name()}.tags{FIELD_MARKER}"
    match_var = Match.create(
        MatchState.tags, ({"d", "c"}, "cd"), (["c", "d"], "list"), "other"
    )
    assert isinstance(match_var, Var)
    assert str(match_var) == (
        f"(() => {{ switch (JSON.stringify([true, pySetCanonical({tags})])) {{"
        'case JSON.stringify([true, pySetCanonical(["c", "d"])]):  return ("cd");  break;'
        'case JSON.stringify([false, ["c", "d"]]):  return ("list");  break;'
        'default:  return ("other");  break;};})()'
    )
    var_data = match_var._get_all_var_data()
    assert var_data is not None
    assert dict(var_data.imports)["$/utils/helpers/set.js"] == (
        ImportVar(tag="pySetCanonical", install=False),
    )

    match_comp = rx.match(
        MatchState.tags, ({"d", "c"}, rx.text("cd")), rx.text("other")
    )
    assert isinstance(match_comp, Component)
    match_child = match_comp.render()["children"][0]
    assert match_child["cond"] == f"[true, pySetCanonical({tags})]"
    assert [conditions for conditions, _ in match_child["match_cases"]] == [
        ['[true, pySetCanonical(["c", "d"])]']
    ]
    assert match_comp._get_all_imports()["$/utils/helpers/set.js"] == [
        ImportVar(tag="pySetCanonical", install=False)
    ]


def test_match_generic_set_var_uses_its_annotation():
    """A generic Var annotated as a set uses the same comparison as a SetVar."""
    result = Match.create(
        Var(_js_expr="tags", _var_type=set[int]), ({1, 2}, "matched"), "other"
    )
    assert str(result) == (
        "(() => { switch (JSON.stringify([true, pySetCanonical(tags)])) {"
        'case JSON.stringify([true, pySetCanonical([1, 2])]):  return ("matched");  break;'
        'default:  return ("other");  break;};})()'
    )


def test_match_optional_set_matches_none():
    """A missing optional set uses the same tag as a literal None case."""
    result = Match.create(
        Var(_js_expr="tags", _var_type=set[str] | None),
        (None, "missing"),
        ({"a"}, "present"),
        "other",
    )
    assert str(result) == (
        "(() => { switch (JSON.stringify([isNotNullOrUndefined(tags), pySetCanonical(tags)])) {"
        'case JSON.stringify([false, null]):  return ("missing");  break;'
        'case JSON.stringify([true, pySetCanonical(["a"])]):  return ("present");  break;'
        'default:  return ("other");  break;};})()'
    )


@pytest.mark.parametrize(
    "var_type", [set[int] | str, frozenset[int] | str, set[int] | str | None]
)
def test_match_mixed_set_subject(var_type):
    """Mixed set subjects choose their comparison tag from the runtime value."""
    result = Match.create(
        Var(_js_expr="tags", _var_type=var_type),
        ({1, 2}, "set"),
        ("ready", "string"),
        (None, "missing"),
        "other",
    )
    assert str(result) == (
        "(() => { switch (JSON.stringify((Array.isArray(tags) ? "
        "[true, pySetCanonical(tags)] : [false, tags]))) {"
        'case JSON.stringify([true, pySetCanonical([1, 2])]):  return ("set");  break;'
        'case JSON.stringify([false, "ready"]):  return ("string");  break;'
        'case JSON.stringify([false, null]):  return ("missing");  break;'
        'default:  return ("other");  break;};})()'
    )
    var_data = result._get_all_var_data()
    assert var_data is not None
    assert dict(var_data.imports)["$/utils/helpers/set.js"] == (
        ImportVar(tag="pySetCanonical", install=False),
    )


@pytest.mark.parametrize("subject_type", [set[int] | str, str])
def test_match_mixed_set_case(subject_type):
    """A mixed set case enables normalization without a literal set case."""
    result = Match.create(
        Var(_js_expr="subject", _var_type=subject_type),
        (Var(_js_expr="caseValue", _var_type=set[int] | str), "matched"),
        "other",
    )
    subject = (
        "(Array.isArray(subject) ? [true, pySetCanonical(subject)] : [false, subject])"
        if subject_type is not str
        else "[false, subject]"
    )
    assert str(result) == (
        f"(() => {{ switch (JSON.stringify({subject})) {{"
        "case JSON.stringify((Array.isArray(caseValue) ? [true, pySetCanonical(caseValue)] "
        ': [false, caseValue])):  return ("matched");  break;'
        'default:  return ("other");  break;};})()'
    )


@pytest.mark.parametrize("as_case", [False, True])
@pytest.mark.parametrize("sequence_type", [list[int], tuple[int, ...], Sequence[int]])
def test_match_rejects_ambiguous_set_sequence_union(as_case, sequence_type):
    """Serialized arrays cannot identify a set within a set-or-list union."""
    mixed = Var(_js_expr="values", _var_type=set[int] | sequence_type)
    with pytest.raises(MatchTypeError) as error:
        Match.create(
            {1} if as_case else mixed, (mixed if as_case else {1}, "set"), "other"
        )
    assert str(error.value) == (
        "rx.match cannot distinguish sets from sequences in a union because both serialize "
        "to arrays. Narrow the var's type before matching."
    )


@pytest.mark.parametrize("as_case", [False, True])
def test_match_custom_set_var_with_tuple_elements(as_case):
    """A custom var's set element type is not mistaken for a union member."""

    class CustomSetVar(Var[set[tuple[int, int]]]):
        """A set annotation retained by a custom var subclass."""

    custom = CustomSetVar(_js_expr="pairs", _var_type=set[tuple[int, int]])
    result = Match.create(
        {(1, 2)} if as_case else custom,
        (custom if as_case else {(1, 2)}, "matched"),
        "other",
    )
    subject = "[[1, 2]]" if as_case else "pairs"
    case = "pairs" if as_case else "[[1, 2]]"
    assert str(result) == (
        f"(() => {{ switch (JSON.stringify([true, pySetCanonical({subject})])) {{"
        f'case JSON.stringify([true, pySetCanonical({case})]):  return ("matched");  break;'
        'default:  return ("other");  break;};})()'
    )


def test_match_on_component_without_default():
    """Test that matching cases with return values as components returns a Fragment
    as the default case if not provided.
    """
    from reflex_components_core.base.fragment import Fragment

    match_case_tuples = (
        (1, rx.text("first value")),
        (2, 3, rx.text("second value")),
    )

    match_comp = rx.match(MatchState.value, *match_case_tuples)
    assert isinstance(match_comp, Component)
    default = match_comp.render()["children"][0]["default"]

    assert isinstance(default, dict)
    assert default["name"] == Fragment.__name__


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
        match=r"rx\.match should have tuples of cases and one default case as the last argument\.",
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
        match=r"A case tuple should have at least a match case element and a return value\.",
    ):
        Match.create(MatchState.value, *match_case)


@pytest.mark.parametrize(
    ("cases", "error_msg"),
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
            (
                'Match cases should have the same return types. Case 3 with return value `"red"` of type '
                "<class 'reflex_base.vars.sequence.LiteralStringVar'> is not <class 'reflex_base.components.component.BaseComponent'>"
            ),
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
            (
                'Match cases should have the same return types. Case 3 with return value `jsx(RadixThemesText,{as:"p"},"first value")` '
                "of type <class 'reflex_components_radix.themes.typography.text.Text'> is not <class 'reflex_base.vars.base.Var'>"
            ),
        ),
    ],
)
def test_match_different_return_types(cases: tuple, error_msg: str):
    """Test that an error is thrown when the return values are of different types.

    Args:
        cases: The match cases.
        error_msg: Expected error message.
    """
    with pytest.raises(MatchTypeError, match=re.escape(error_msg)):
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
    with pytest.raises(
        ValueError,
        match=r"rx\.match should have tuples of cases and one default case as the last argument\.",
    ):
        Match.create(MatchState.value, *match_case)


def test_match_no_cond():
    with pytest.raises(ValueError):
        _ = Match.create(None)  # pyright: ignore [reportCallIssue]
