import pytest

from nextpy.core import style
from nextpy.core.vars import Var

test_style = [
    ({"a": 1}, {"a": 1}),
    ({"a": Var.create("abc")}, {"a": "abc"}),
    ({"test_case": 1}, {"testCase": 1}),
    ({"test_case": {"a": 1}}, {"testCase": {"a": 1}}),
]


@pytest.mark.parametrize(
    "style_dict,expected",
    test_style,
)
def test_convert(style_dict, expected):
    """Test Format a style dictionary.

    Args:
        style_dict: The style to check.
        expected: The expected formatted style.
    """
    assert style.convert(style_dict) == expected


@pytest.mark.parametrize(
    "style_dict,expected",
    test_style,
)
def test_create_style(style_dict, expected):
    """Test style dictionary.

    Args:
        style_dict: The style to check.
        expected: The expected formatted style.
    """
    assert style.Style(style_dict) == expected
