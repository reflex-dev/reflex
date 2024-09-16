import pytest

from reflex.components.base.bare import Bare
from reflex.vars.base import Var

STATE_VAR = Var(_js_expr="default_state.name")


@pytest.mark.parametrize(
    "contents,expected",
    [
        ("hello", '{"hello"}'),
        ("{}", '{"{}"}'),
        (None, '{""}'),
        (STATE_VAR, "{default_state.name}"),
        # This behavior is now unsupported.
        # ("${default_state.name}", "${default_state.name}"),
        # ("{state.name}", "{state.name}"),
    ],
)
def test_fstrings(contents, expected):
    """Test that fstrings are rendered correctly.

    Args:
        contents: The contents of the component.
        expected: The expected output.
    """
    comp = Bare.create(contents).render()
    assert comp["contents"] == expected
