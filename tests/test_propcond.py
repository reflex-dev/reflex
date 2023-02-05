from typing import Any

import pytest

from pynecone.propcond import PropCond
from pynecone.utils import wrap
from pynecone.var import BaseVar


@pytest.mark.parametrize(
    "prop1,prop2",
    [
        (1, 3),
        (1, "text"),
        ("text1", "text2"),
    ],
)
def test_validate_propcond(prop1: Any, prop2: Any):
    """Test the creation of conditional props.

    Args:
        prop1: truth condition value
        prop2: false condition value

    """
    prop_cond = PropCond.create(
        cond=BaseVar(name="cond_state.value", type_=str), prop1=prop1, prop2=prop2
    )

    expected_prop1 = wrap(prop1, "'") if isinstance(prop1, str) else prop1
    expected_prop2 = wrap(prop2, "'") if isinstance(prop2, str) else prop2

    assert str(prop_cond) == (
        "{cond_state.value ? " f"{expected_prop1} : " f"{expected_prop2}" "}"
    )
