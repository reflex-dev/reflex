import pytest

from pynecone.components.base.bare import Bare
from pynecone.state import DefaultState


@pytest.mark.parametrize(
    "contents,expected",
    [
        ("hello", "hello"),
        ("{}", "{}"),
        ("{default_state.name}", "${default_state.name}"),
        ("{state.name}", "{state.name}"),
    ],
)
def test_fstrings(contents, expected):
    """Test that fstrings are rendered correctly.

    Args:
        contents: The contents of the component.
        expected: The expected output.
    """
    comp = Bare.create(contents)
    comp.set_state(DefaultState)
    assert str(comp) == f"{{`{expected}`}}"
