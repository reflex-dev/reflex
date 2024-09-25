import json
from typing import Any, Union

import pytest

from reflex.components.base.fragment import Fragment
from reflex.components.core.cond import Cond, cond
from reflex.components.radix.themes.typography.text import Text
from reflex.state import BaseState, State
from reflex.utils.format import format_state_name
from reflex.vars.base import LiteralVar, Var, computed_var


@pytest.fixture
def cond_state(request):
    class CondState(BaseState):
        value: request.param["value_type"] = request.param["value"]  # noqa

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
        cond_state.value,
        Text.create("cond is True"),
        Text.create("cond is False"),
    )
    cond_dict = cond_component.render() if type(cond_component) == Fragment else {}
    assert cond_dict["name"] == "Fragment"

    [condition] = cond_dict["children"]
    assert condition["cond_state"] == f"isTrue({cond_state.get_full_name()}.value)"

    # true value
    true_value = condition["true_value"]
    assert true_value["name"] == "Fragment"

    [true_value_text] = true_value["children"]
    assert true_value_text["name"] == "RadixThemesText"
    assert true_value_text["children"][0]["contents"] == '{"cond is True"}'

    # false value
    false_value = condition["false_value"]
    assert false_value["name"] == "Fragment"

    [false_value_text] = false_value["children"]
    assert false_value_text["name"] == "RadixThemesText"
    assert false_value_text["children"][0]["contents"] == '{"cond is False"}'


@pytest.mark.parametrize(
    "c1, c2",
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
    assert str(prop_cond) == f"(true ? {str(c1)} : {str(c2)})"


def test_cond_no_mix():
    """Test if cond can't mix components and props."""
    with pytest.raises(ValueError):
        cond(True, LiteralVar.create("hello"), Text.create("world"))


def test_cond_no_else():
    """Test if cond can be used without else."""
    # Components should support the use of cond without else
    comp = cond(True, Text.create("hello"))
    assert isinstance(comp, Fragment)
    comp = comp.children[0]
    assert isinstance(comp, Cond)
    assert comp.cond._decode() is True  # type: ignore
    assert comp.comp1.render() == Fragment.create(Text.create("hello")).render()
    assert comp.comp2 == Fragment.create()

    # Props do not support the use of cond without else
    with pytest.raises(ValueError):
        cond(True, "hello")  # type: ignore


def test_cond_computed_var():
    """Test if cond works with computed vars."""

    class CondStateComputed(State):
        @computed_var
        def computed_int(self) -> int:
            return 0

        @computed_var
        def computed_str(self) -> str:
            return "a string"

    comp = cond(True, CondStateComputed.computed_int, CondStateComputed.computed_str)

    # TODO: shouln't this be a ComputedVar?
    assert isinstance(comp, Var)

    state_name = format_state_name(CondStateComputed.get_full_name())
    assert (
        str(comp) == f"(true ? {state_name}.computed_int : {state_name}.computed_str)"
    )

    assert comp._var_type == Union[int, str]
