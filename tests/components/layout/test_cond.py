import pytest

import pynecone as pc


@pytest.fixture
def cond_state(request):
    class CondState(pc.State):
        value: request.param["value_type"] = request.param["value"]

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
    """Test if cond can be a pc.Val with any values"""
    cond_component = pc.cond(
        cond_state.value,
        pc.text("cond is True"),
        pc.text("cond is False"),
    )

    rendered_cond = cond_component._render()

    assert str(rendered_cond) == (
        "{cond_state.value ? "
        "<Text>{`cond is True`}</Text> : "
        "<Text>{`cond is False`}</Text>}"
    )
