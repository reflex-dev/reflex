import pytest

import pynecone as pc
from pynecone.components.layout.cond import Cond
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
    """Test if cond can be a pc.Val with any values

    Args:
        cond_state: A fixture.
    """
    cond_component = Cond.create(
        cond_state.value,
        Text.create("cond is True"),
        Text.create("cond is False"),
    )

    assert str(cond_component) == (
        "{cond_state.value ? "
        "<Text>{`cond is True`}</Text> : "
        "<Text>{`cond is False`}</Text>}"
    )
