import json
from typing import Any, Literal

import pytest
from reflex_base.components.component import Component
from reflex_base.constants.state import FIELD_MARKER
from reflex_base.utils.format import format_state_name
from reflex_base.vars.base import LiteralVar, Var, computed_var
from reflex_components_core.base.fragment import Fragment
from reflex_components_core.core.cond import Cond, cond
from reflex_components_radix.themes.typography.text import Text
from typing_extensions import assert_type

from reflex.state import BaseState


@pytest.fixture
def cond_state(request):
    class CondState(BaseState):
        value: request.param["value_type"] = request.param["value"]  # pyright: ignore [reportInvalidTypeForm, reportUndefinedVariable] # noqa: F821

    return CondState


def test_f_string_cond_interpolation():
    # make sure backticks inside interpolation don't get escaped
    var = LiteralVar.create(f"x {cond(True, 'a', 'b')}")
    assert str(var) == '("x "+(true ? "a" : "b"))'


@pytest.mark.parametrize(
    "cond_state",
    [
        pytest.param({"value_type": bool, "value": True}),
        pytest.param({"value_type": int, "value": 0}),
        pytest.param({"value_type": str, "value": "true"}),
    ],
    indirect=True,
)
def test_validate_cond(cond_state: BaseState):
    """Test if cond can be a rx.Var with any values.

    Args:
        cond_state: A fixture.
    """
    cond_component = cond(
        cond_state.value,  # pyright: ignore[reportAttributeAccessIssue]
        Text.create("cond is True"),
        Text.create("cond is False"),
    )
    cond_dict = cond_component.render() if type(cond_component) is Fragment else {}
    assert cond_dict["name"] == "Fragment"

    [condition] = cond_dict["children"]
    assert condition["cond_state"] == str(cond_state.value.bool())  # pyright: ignore[reportAttributeAccessIssue]

    # true value
    true_value = condition["true_value"]
    assert true_value["name"] == "Fragment"

    [true_value_text] = true_value["children"]
    assert true_value_text["name"] == "RadixThemesText"
    assert true_value_text["children"][0]["contents"] == '"cond is True"'

    # false value
    false_value = condition["false_value"]
    assert false_value["name"] == "Fragment"

    [false_value_text] = false_value["children"]
    assert false_value_text["name"] == "RadixThemesText"
    assert false_value_text["children"][0]["contents"] == '"cond is False"'


@pytest.mark.parametrize(
    ("c1", "c2"),
    [
        (True, False),
        (32, 0),
        ("hello", ""),
        (2.3, 0.0),
        (LiteralVar.create("a"), LiteralVar.create("b")),
    ],
)
def test_prop_cond(c1: Any, c2: Any):
    """Test if cond can be a prop.

    Args:
        c1: truth condition value
        c2: false condition value
    """
    prop_cond = cond(
        True,
        c1,
        c2,
    )

    assert isinstance(prop_cond, Var)
    if not isinstance(c1, Var):
        c1 = json.dumps(c1)
    if not isinstance(c2, Var):
        c2 = json.dumps(c2)
    assert str(prop_cond) == f"(true ? {c1!s} : {c2!s})"


def test_cond_no_mix():
    """Test if cond can mix components and props."""
    cond(True, LiteralVar.create("hello"), Text.create("world"))


def test_cond_no_else():
    """Test if cond can be used without else."""
    # Components should support the use of cond without else
    comp = cond(True, Text.create("hello"))
    assert isinstance(comp, Fragment)
    comp = comp.children[0]
    assert isinstance(comp, Cond)
    assert comp.cond._decode() is True
    assert comp.children[0].render() == Fragment.create(Text.create("hello")).render()  # pyright: ignore [reportOptionalMemberAccess]
    assert comp.children[1] == Fragment.create()

    # Props do not support the use of cond without else
    with pytest.raises(ValueError):
        cond(True, "hello")  # pyright: ignore [reportArgumentType]


def test_cond_computed_var():
    """Test if cond works with computed vars."""

    class CondStateComputed(BaseState):
        @computed_var
        def computed_int(self) -> int:
            return 0

        @computed_var
        def computed_str(self) -> str:
            return "a string"

    comp = cond(True, CondStateComputed.computed_int, CondStateComputed.computed_str)

    # TODO: shouldn't this be a ComputedVar?
    assert isinstance(comp, Var)

    state_name = format_state_name(CondStateComputed.get_full_name())
    assert (
        str(comp)
        == f"(true ? {state_name}.computed_int{FIELD_MARKER} : {state_name}.computed_str{FIELD_MARKER})"
    )

    assert comp._var_type == int | str


def test_cond_assert_types() -> None:
    """Test that pyright infers the correct return types for cond overloads."""
    text_comp = Text.create("hello")
    text_comp2 = Text.create("world")
    var_int: Var[int] = LiteralVar.create(1)
    var_str: Var[str] = LiteralVar.create("a")

    # Component, Component -> Component
    _ = assert_type(cond(True, text_comp, text_comp2), Component)

    # Component, non-component -> Component
    _ = assert_type(cond(True, text_comp, "fallback"), Component)

    # Component only (no else) -> Component
    _ = assert_type(cond(True, text_comp), Component)

    # non-component, Component -> Component
    _ = assert_type(cond(True, "hello", text_comp), Component)

    # T, T -> Var[T]
    _ = assert_type(cond(True, "hello", "world"), Var[str])

    # T, U -> Var[T | U]
    _ = assert_type(cond(True, "hello", 3), Var[str | int])

    # T, Var[T] -> Var[T]
    _ = assert_type(cond(True, "hello", var_str), Var[str])

    # Var[T], T -> Var[T]
    _ = assert_type(cond(True, var_str, "world"), Var[str])

    # T, Var[U] -> Var[T | U]
    _ = assert_type(cond(True, "hello", var_int), Var[str | int])

    # Var[T], U -> Var[T | U]
    _ = assert_type(cond(True, var_str, 3), Var[int | Literal["a"]])

    # Var[T], Var[U] -> Var[T | U]
    _ = assert_type(cond(True, var_int, var_str), Var[int | Literal["a"]])
