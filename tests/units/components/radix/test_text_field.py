import pytest
from reflex_base.vars.base import Var
from reflex_components_core.el import elements
from reflex_components_radix.themes.components.text_field import TextFieldRoot

import reflex as rx


def test_hidden_type_renders_a_plain_input():
    """A hidden input has no wrapper to keep it off the page.

    https://github.com/reflex-dev/reflex/issues/6874
    """
    component = rx.input(type="hidden", value="foo")

    assert type(component) is elements.Input
    assert "TextField.Root" not in component.render()["name"]


def test_hidden_prop_renders_a_plain_input():
    """A statically hidden input renders without the Radix wrapper."""
    component = rx.input(hidden=True, value="foo")

    assert type(component) is elements.Input


def test_visible_input_still_uses_the_radix_root():
    """A normal input keeps the Radix wrapper and its styling."""
    component = rx.input(placeholder="Name")

    assert isinstance(component, TextFieldRoot)


def test_hidden_type_as_a_var_keeps_the_radix_root():
    """The value is only known at runtime, so the wrapper has to stay."""
    component = rx.input(type=Var(_js_expr="inputType", _var_type=str))

    assert isinstance(component, TextFieldRoot)


def test_hidden_input_with_radix_props_keeps_the_radix_root():
    """`size` and friends do not exist on the plain element."""
    component = rx.input(type="hidden", size="2")

    assert isinstance(component, TextFieldRoot)


def test_hidden_input_is_still_accepted_by_form_control():
    """A hidden input stays usable inside `rx.form.control`."""
    control = rx.form.control(rx.input(type="hidden", value="foo"))

    assert type(control.children[0]) is elements.Input


def test_form_control_still_rejects_a_non_input_child():
    """Widening the guard to plain inputs must not let anything through."""
    with pytest.raises(TypeError):
        rx.form.control(rx.text("not an input"))
