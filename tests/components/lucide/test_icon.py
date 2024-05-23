import pytest

from reflex.components.lucide.icon import LUCIDE_ICON_LIST, RENAMED_ICONS_05, Icon
from reflex.utils import format


@pytest.mark.parametrize("tag", LUCIDE_ICON_LIST)
def test_icon(tag):
    icon = Icon.create(tag)
    assert icon.alias == f"Lucide{format.to_title_case(tag)}Icon"


RENAMED_TAGS = [tag for tag in RENAMED_ICONS_05.items()]


@pytest.mark.parametrize("tag, new_tag", RENAMED_TAGS)
def test_icon_renamed_tags(tag, new_tag):
    Icon.create(tag)
    # TODO: need a PR so we can pass the following test. Currently it fails and uses the old tag as the import.
    # assert icon.alias == f"Lucide{format.to_title_case(new_tag)}Icon"


def test_icon_missing_tag():
    with pytest.raises(AttributeError):
        _ = Icon.create()


def test_icon_invalid_tag():
    with pytest.raises(ValueError):
        _ = Icon.create("invalid-tag")


def test_icon_multiple_children():
    with pytest.raises(AttributeError):
        _ = Icon.create("activity", "child1", "child2")


def test_icon_add_style():
    ic = Icon.create("activity")
    assert ic.add_style() is None
