import pytest
from reflex_base.style import Style
from reflex_base.vars.base import LiteralVar
from reflex_components_lucide.icon import Icon
from reflex_components_radix.themes.components.icon_button import IconButton


def test_icon_button():
    ib1 = IconButton.create("activity")
    assert isinstance(ib1, IconButton)

    ib2 = IconButton.create(Icon.create("activity"))
    assert isinstance(ib2, IconButton)

    assert isinstance(ib1.add_style(), Style)
    assert isinstance(ib2.add_style(), Style)


def test_icon_button_no_child():
    with pytest.raises(ValueError):
        _ = IconButton.create()


def test_icon_button_size_prop():
    ib1 = IconButton.create("activity", size="2")
    assert isinstance(ib1, IconButton)

    ib2 = IconButton.create("activity", size=LiteralVar.create("2"))
    assert isinstance(ib2, IconButton)
