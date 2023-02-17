import pytest

from pynecone import utils
from pynecone.components.media.icon import ICON_LIST, Icon


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
    assert icon.tag == utils.to_title_case(tag) + "Icon"


@pytest.mark.parametrize("tag", ["", " ", "invalid", 123])
def test_invalid_icon(tag):
    """Test that an invalid icon raises an error.

    Args:
        tag: The icon tag.
    """
    with pytest.raises(ValueError):
        Icon.create(tag=tag)
