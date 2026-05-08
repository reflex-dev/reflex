from reflex_components_core.base.fragment import Fragment
from reflex_components_lucide.icon import Icon
from reflex_components_radix.themes.components.callout import (
    Callout,
    CalloutIcon,
    CalloutRoot,
    CalloutText,
)


def test_callout_create_without_icon():
    component = Callout.create("You will need admin privileges.")

    assert isinstance(component, CalloutRoot)
    assert len(component.children) == 2
    assert isinstance(component.children[0], Fragment)
    assert isinstance(component.children[1], CalloutText)


def test_callout_create_with_icon():
    component = Callout.create("You will need admin privileges.", icon="info")

    assert isinstance(component, CalloutRoot)
    assert len(component.children) == 2
    assert isinstance(component.children[0], CalloutIcon)
    assert isinstance(component.children[0].children[0], Icon)
    assert isinstance(component.children[1], CalloutText)
