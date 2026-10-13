from typing import TypedDict

import pytest
from reflex_base.event import EventChain
from reflex_base.utils.exceptions import EventHandlerValueError
from reflex_components_core.el.elements.forms import Form as HTMLForm
from reflex_components_radix.themes.components.checkbox_cards import checkbox_cards

import reflex as rx


class ColorState(rx.State):
    """State used to exercise checkbox_cards' controlled value/on_value_change."""

    colors: list[str] = ["red"]

    @rx.event
    def on_colors_change(self, value: list[str]):
        """Store the newly checked values.

        Args:
            value: The updated set of checked card values.
        """
        self.colors = value


class SignupData(TypedDict):
    """Submit payload naming the checkbox cards field."""

    colors: str


class SignupState(rx.State):
    """State with a TypedDict-annotated submit handler."""

    @rx.event
    def on_submit(self, form_data: SignupData):
        """Accept the submitted form.

        Args:
            form_data: The submitted form data.
        """


def test_checkbox_cards_renders_value_props():
    """The root renders name and default_value, and the item renders its value."""
    root = checkbox_cards.root(
        checkbox_cards.item("Red", value="red"),
        name="colors",
        default_value=["red"],
    )
    rendered = root.render()

    assert 'name:"colors"' in rendered["props"]
    assert 'defaultValue:["red"]' in rendered["props"]
    assert 'value:"red"' in rendered["children"][0]["props"]


def test_checkbox_cards_root_renders_controlled_value_and_on_value_change():
    """The root binds the controlled value and forwards the checked values."""
    root = checkbox_cards.root(
        checkbox_cards.item("Red", value="red"),
        value=ColorState.colors,
        on_value_change=ColorState.on_colors_change,
    )
    props = root.render()["props"]

    assert f"value:{ColorState.colors!s}" in props
    on_value_change = next(p for p in props if p.startswith("onValueChange:"))
    assert 'on_colors_change", ({ ["value"] : _ev_0 })' in on_value_change


def test_on_submit_accepts_typed_dict_matching_checkbox_cards_name():
    """A TypedDict field matching the checkbox cards name validates."""
    form = HTMLForm.create(
        checkbox_cards.root(
            checkbox_cards.item("Red", value="red"),
            name="colors",
        ),
        on_submit=SignupState.on_submit,
    )

    assert isinstance(form.event_triggers["on_submit"], EventChain)


def test_on_submit_typed_dict_missing_checkbox_cards_field_raises():
    """A TypedDict field without a matching checkbox cards name raises."""
    with pytest.raises(EventHandlerValueError):
        HTMLForm.create(
            checkbox_cards.root(
                checkbox_cards.item("Red", value="red"),
                name="wrong_field",
            ),
            on_submit=SignupState.on_submit,
        )
