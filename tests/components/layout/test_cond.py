import json
from typing import Any

import pytest

import pynecone as pc
from pynecone.components.layout.box import Box
from pynecone.components.layout.cond import Cond, cond
from pynecone.components.layout.fragment import Fragment
from pynecone.components.layout.responsive import (
    desktop_only,
    mobile_and_tablet,
    mobile_only,
    tablet_and_desktop,
    tablet_only,
)
from pynecone.components.typography.text import Text
from pynecone.vars import Var


@pytest.fixture
def cond_state(request):
    class CondState(pc.State):
        value: request.param["value_type"] = request.param["value"]  # noqa

    return CondState


@pytest.mark.parametrize(
    "cond_state",
    [
        pytest.param({"value_type": bool, "value": True}),
        pytest.param({"value_type": int, "value": 0}),
        pytest.param({"value_type": str, "value": "true"}),
    ],
    indirect=True,
)
def test_validate_cond(cond_state: pc.Var):
    """Test if cond can be a pc.Var with any values.

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
    assert condition["cond_state"] == "isTrue(cond_state.value)"

    # true value
    true_value = condition["true_value"]
    assert true_value["name"] == "Fragment"

    [true_value_text] = true_value["children"]
    assert true_value_text["name"] == "Text"
    assert true_value_text["children"][0]["contents"] == "{`cond is True`}"

    # false value
    false_value = condition["false_value"]
    assert false_value["name"] == "Fragment"

    [false_value_text] = false_value["children"]
    assert false_value_text["name"] == "Text"
    assert false_value_text["children"][0]["contents"] == "{`cond is False`}"


@pytest.mark.parametrize(
    "c1, c2",
    [
        (True, False),
        (32, 0),
        ("hello", ""),
        (2.3, 0.0),
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
    c1 = json.dumps(c1).replace('"', "`")
    c2 = json.dumps(c2).replace('"', "`")
    assert str(prop_cond) == f"{{isTrue(true) ? {c1} : {c2}}}"


def test_cond_no_else():
    """Test if cond can be used without else."""
    # Components should support the use of cond without else
    comp = cond(True, Text.create("hello"))
    assert isinstance(comp, Fragment)
    comp = comp.children[0]
    assert isinstance(comp, Cond)
    assert comp.cond == True  # noqa
    assert comp.comp1 == Fragment.create(Text.create("hello"))
    assert comp.comp2 == Fragment.create()

    # Props do not support the use of cond without else
    with pytest.raises(ValueError):
        cond(True, "hello")


def test_mobile_only():
    """Test the mobile_only responsive component."""
    component = mobile_only("Content")
    assert isinstance(component, Box)


def test_tablet_only():
    """Test the tablet_only responsive component."""
    component = tablet_only("Content")
    assert isinstance(component, Box)


def test_desktop_only():
    """Test the desktop_only responsive component."""
    component = desktop_only("Content")
    assert isinstance(component, Box)


def test_tablet_and_desktop():
    """Test the tablet_and_desktop responsive component."""
    component = tablet_and_desktop("Content")
    assert isinstance(component, Box)


def test_mobile_and_tablet():
    """Test the mobile_and_tablet responsive component."""
    component = mobile_and_tablet("Content")
    assert isinstance(component, Box)
