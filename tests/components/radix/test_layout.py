from reflex.components.radix.themes.layout.base import LayoutComponent


def test_layout_component():
    lc = LayoutComponent.create()
    assert isinstance(lc, LayoutComponent)
