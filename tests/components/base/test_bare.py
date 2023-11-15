import pytest

from nextpy.components.base.bare import Bare


@pytest.mark.parametrize(
    "contents,expected",
    [
        ("hello", "hello"),
        ("{}", "{}"),
        ("${default_state.name}", "${default_state.name}"),
        ("{state.name}", "{state.name}"),
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
