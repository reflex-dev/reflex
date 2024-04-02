import pytest

from reflex.components.radix.themes.base import Theme
from reflex.components.radix.themes.components.icon_button import IconButton
from reflex.vars import Var


def test_icon_button():
    ib = IconButton.create("activity")
    assert isinstance(ib, IconButton)

    ib._apply_theme(Theme.create())


def test_icon_button_no_child():
    with pytest.raises(ValueError):
        _ = IconButton.create()


def test_icon_button_size_prop():
    ib1 = IconButton.create("activity", size="2")
    assert isinstance(ib1, IconButton)

    ib2 = IconButton.create("activity", size=Var.create("2"))
    assert isinstance(ib2, IconButton)
