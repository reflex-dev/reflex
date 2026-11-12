import pytest
from reflex_base.components.component import Component
from reflex_base.vars.base import Var
from reflex_components_core.base.bare import Bare
from reflex_components_core.base.fragment import Fragment
from reflex_components_core.core.cond import cond
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
    assert "icon" not in component.style


@pytest.mark.parametrize(
    "icon",
    [
        Icon.create(tag="info"),
        cond(
            Var(_js_expr="is_error", _var_type=bool),
            Icon.create(tag="octagon_x"),
            Icon.create(tag="info"),
        ),
    ],
)
def test_callout_create_with_icon_component(icon: Component):
    component = Callout.create("You will need admin privileges.", icon=icon)

    assert isinstance(component.children[0], CalloutIcon)
    assert component.children[0].children[0] is icon
    assert "icon" not in component.style


def test_callout_create_with_component_var_icon():
    # An @rx.memo argument typed rx.Var[rx.Component] arrives as a ComponentVar.
    icon = Var(_js_expr="custom_icon", _var_type=Component).guess_type()
    component = Callout.create("You will need admin privileges.", icon=icon)

    assert isinstance(component.children[0], CalloutIcon)
    # A Var child is wrapped in a Bare component.
    bare = component.children[0].children[0]
    assert isinstance(bare, Bare)
    assert bare.contents is icon
    assert "icon" not in component.style
