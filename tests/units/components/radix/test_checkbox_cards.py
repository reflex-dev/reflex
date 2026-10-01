from typing import TypedDict

import pytest
from reflex_base.event import EventChain
from reflex_base.utils.exceptions import EventHandlerValueError
from reflex_components_core.el.elements.forms import Form as HTMLForm
from reflex_components_radix.themes.components.checkbox_cards import (
    CheckboxCardsRoot,
    checkbox_cards,
)

import reflex as rx


def test_checkbox_cards_item_accepts_value_and_disabled():
    """checkbox_cards.item previously had no declared props at all -- it could
    not even be given a value, so it was unusable for real form submission.
    """
    item = checkbox_cards.item("Red", value="red", disabled=True, required=True)
    props = item.render()["props"]

    assert 'value:"red"' in props
    assert "disabled:true" in props
    assert "required:true" in props


def test_checkbox_cards_root_renders_native_form_props():
    """checkbox_cards.root was missing name/disabled/required/value/etc. entirely,
    unlike its sibling radio_cards.root which already exposes them.
    """
    root = checkbox_cards.root(
        checkbox_cards.item("Red", value="red"),
        name="colors",
        default_value=["red"],
        disabled=False,
        required=True,
        dir="ltr",
        orientation="vertical",
        loop=True,
    )
    props = root.render()["props"]

    assert 'name:"colors"' in props
    assert 'defaultValue:["red"]' in props
    assert "disabled:false" in props
    assert "required:true" in props
    assert 'dir:"ltr"' in props
    assert 'orientation:"vertical"' in props
    assert "loop:true" in props


def test_checkbox_cards_root_renders_controlled_value_and_on_value_change():
    """checkbox_cards.root previously could not be used as a controlled
    component at all -- value/on_value_change did not exist as props.
    """

    class ColorState(rx.State):
        colors: list[str] = ["red"]

        @rx.event
        def on_colors_change(self, value: list[str]):
            self.colors = value

    root = checkbox_cards.root(
        checkbox_cards.item("Red", value="red"),
        value=ColorState.colors,
        on_value_change=ColorState.on_colors_change,
    )
    props = root.render()["props"]

    assert any(p.startswith("value:") for p in props)
    assert any(p.startswith("onValueChange:") for p in props)


def test_checkbox_cards_root_is_form_control():
    """Newly marked, matching checkbox_group/radio_cards, so a static name= is
    now collected by TypedDict validation on a form's on_submit handler.
    """
    assert CheckboxCardsRoot._is_form_control is True


def test_checkbox_cards_root_has_no_as_child_prop():
    """Radix Themes deliberately excludes asChild from CheckboxCards.Root
    (ComponentPropsWithout<..., 'asChild' | 'color' | 'defaultChecked'> in
    checkbox-cards.tsx): with as_child=True the Root merges into its first
    child instead of rendering its own grid/group element. It must not be
    a declared field here.
    """
    assert "as_child" not in CheckboxCardsRoot.get_fields()


def test_on_submit_accepts_typed_dict_matching_checkbox_cards_name():
    """A TypedDict on_submit contract naming a checkbox_cards.root's name= must
    validate successfully now that CheckboxCardsRoot reports it as a form field.
    """

    class SignupData(TypedDict):
        colors: list[str]

    class SignupState(rx.State):
        @rx.event
        def on_submit(self, form_data: SignupData):
            pass

    form = HTMLForm.create(
        checkbox_cards.root(
            checkbox_cards.item("Red", value="red"),
            name="colors",
        ),
        on_submit=SignupState.on_submit,
    )

    assert isinstance(form.event_triggers["on_submit"], EventChain)


def test_on_submit_typed_dict_missing_checkbox_cards_field_raises():
    """The same contract without a matching name= must still fail loudly."""

    class SignupData(TypedDict):
        colors: list[str]

    class SignupState(rx.State):
        @rx.event
        def on_submit(self, form_data: SignupData):
            pass

    with pytest.raises(EventHandlerValueError):
        HTMLForm.create(
            checkbox_cards.root(
                checkbox_cards.item("Red", value="red"),
                name="wrong_field",
            ),
            on_submit=SignupState.on_submit,
        )
