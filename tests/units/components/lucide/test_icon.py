import pytest

from reflex.components.lucide.icon import (
    LUCIDE_ICON_LIST,
    LUCIDE_ICON_MAPPING_OVERRIDE,
    Icon,
)
from reflex.utils import format


@pytest.mark.parametrize("tag", LUCIDE_ICON_LIST)
def test_icon(tag):
    icon = Icon.create(tag)
    assert icon.alias == "Lucide" + LUCIDE_ICON_MAPPING_OVERRIDE.get(
        tag, format.to_title_case(tag)
    )


def test_icon_missing_tag():
    with pytest.raises(AttributeError):
        _ = Icon.create()


def test_icon_invalid_tag():
    invalid = Icon.create("invalid-tag")
    assert invalid.tag == "CircleHelp"


def test_icon_multiple_children():
    with pytest.raises(AttributeError):
        _ = Icon.create("activity", "child1", "child2")


def test_icon_add_style():
    ic = Icon.create("activity")
    assert ic.add_style() is None
