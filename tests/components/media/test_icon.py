import pytest

from nextpy.components.media.icon import ICON_LIST, Icon
from nextpy.utils import format


def test_no_tag_errors():
    """Test that an icon without a tag raises an error."""
    with pytest.raises(AttributeError):
        Icon.create()


def test_children_errors():
    """Test that an icon with children raises an error."""
    with pytest.raises(AttributeError):
        Icon.create("child", tag="search")


@pytest.mark.parametrize(
    "tag",
    ICON_LIST,
)
def test_valid_icon(tag: str):
    """Test that a valid icon does not raise an error.

    Args:
        tag: The icon tag.
    """
    icon = Icon.create(tag=tag)
    assert icon.tag == format.to_title_case(tag) + "Icon"


@pytest.mark.parametrize("tag", ["", " ", "invalid", 123])
def test_invalid_icon(tag):
    """Test that an invalid icon raises an error.

    Args:
        tag: The icon tag.
    """
    with pytest.raises(ValueError):
        Icon.create(tag=tag)


@pytest.mark.parametrize(
    "tag",
    ["Check", "Close", "eDit"],
)
def test_tag_with_capital(tag: str):
    """Test that an icon that tag with capital does not raise an error.

    Args:
        tag: The icon tag.
    """
    icon = Icon.create(tag=tag)
    assert icon.tag == format.to_title_case(tag) + "Icon"
