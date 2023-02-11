from typing import Any

import pytest
import pytest_mock

import pynecone as pc
from pynecone.components import cond
from pynecone.components.layout.cond import Cond
from pynecone.components.layout.foreach import Foreach
from pynecone.components.layout.fragment import Fragment
from pynecone.components.tags.tag import PropCond
from pynecone.components.typography.text import Text


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
    """Test if cond can be a pc.Val with any values.

    Args:
        cond_state: A fixture.
    """
    cond_component = cond(
        cond_state.value,
        Text.create("cond is True"),
        Text.create("cond is False"),
    )

    assert str(cond_component) == (
        "{cond_state.value ? "
        "<Text>{`cond is True`}</Text> : "
        "<Text>{`cond is False`}</Text>}"
    )


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

    assert isinstance(prop_cond, PropCond)
    assert prop_cond.prop1 == c1
    assert prop_cond.prop2 == c2
    assert prop_cond.cond == True  # noqa


def test_cond_no_else():
    """Test if cond can be used without else."""
    # Components should support the use of cond without else
    comp = cond(True, Text.create("hello"))
    assert isinstance(comp, Cond)
    assert comp.cond == True  # noqa
    assert comp.comp1 == Text.create("hello")
    assert comp.comp2 == Fragment.create()

    # Props do not support the use of cond without else
    with pytest.raises(ValueError):
        cond(True, "hello")


def test_cond_foreach(mocker: pytest_mock.MockFixture):
    var_name = "abc"
    mocker.patch("pynecone.utils.get_unique_variable_name", return_value=var_name)

    cond_component = Cond.create(
        True,  # pyright: reportGeneralTypeIssues=false
        Foreach.create(
            ["Tommy", "is", "cool"],  # pyright: reportGeneralTypeIssues=false
            lambda x: Text.create(x),
        ),
        Text.create("anything else"),
    )

    assert str(cond_component) == (
        f'{{true ? ["Tommy", "is", "cool"].map(({var_name}, i) => <Text key={{i}}>{{{var_name}}}</Text>) : <Text>{{`anything else`}}</Text>}}'
    )
