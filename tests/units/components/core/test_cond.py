import json
from typing import Any, Union

import pytest

from reflex.components.core.cond import cond
from reflex.components.radix.themes.typography.text import Text
from reflex.state import BaseState
from reflex.utils.format import format_state_name
from reflex.vars.base import LiteralVar, Var, computed_var


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
    first_component = Text.create("cond is True")
    second_component = Text.create("cond is False")
    cond_var = cond(
        cond_state.value,
        first_component,
        second_component,
    )

    assert isinstance(cond_var, Var)
    assert (
        str(cond_var)
        == f'({cond_state.value.bool()!s} ? (jsx(RadixThemesText, ({{ ["as"] : "p" }}), (jsx(Fragment, ({{  }}), "cond is True")))) : (jsx(RadixThemesText, ({{ ["as"] : "p" }}), (jsx(Fragment, ({{  }}), "cond is False")))))'
    )

    var_data = cond_var._get_all_var_data()
    assert var_data is not None
    assert var_data.components == (first_component, second_component)


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
    assert str(prop_cond) == f"(true ? {c1!s} : {c2!s})"


def test_cond_mix():
    """Test if cond can mix components and props."""
    x = cond(True, LiteralVar.create("hello"), Text.create("world"))
    assert isinstance(x, Var)
    assert (
        str(x)
        == '(true ? "hello" : (jsx(RadixThemesText, ({ ["as"] : "p" }), (jsx(Fragment, ({  }), "world")))))'
    )


def test_cond_no_else():
    """Test if cond can be used without else."""
    # Components should support the use of cond without else
    comp = cond(True, Text.create("hello"))
    assert isinstance(comp, Var)
    assert (
        str(comp)
        == '(true ? (jsx(RadixThemesText, ({ ["as"] : "p" }), (jsx(Fragment, ({  }), "hello")))) : (jsx(Fragment, ({  }))))'
    )

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
        str(comp) == f"(true ? {state_name}.computed_int : {state_name}.computed_str)"
    )

    assert comp._var_type == Union[int, str]
