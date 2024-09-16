import pytest

from reflex.components.lucide.icon import Icon
from reflex.components.radix.themes.components.icon_button import IconButton
from reflex.style import Style
from reflex.vars.base import LiteralVar


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
