from reflex_components_radix.themes.components.checkbox_group import (
    CheckboxGroupRoot,
    checkbox_group,
)

import reflex as rx


class ColorState(rx.State):
    """State used to exercise checkbox_group's controlled value/on_value_change."""

    colors: list[str] = ["red"]

    @rx.event
    def on_colors_change(self, value: list[str]):
        """Store the newly checked values.

        Args:
            value: The updated set of checked checkbox values.
        """
        self.colors = value


def test_checkbox_group_root_renders_native_form_props():
    """value/on_value_change/disabled/required/dir/orientation/loop must all render.

    These mirror the props radio_group.root already exposes for the analogous
    Radix primitive; checkbox_group.root was missing all of them.
    """
    root = checkbox_group.root(
        checkbox_group.item("Red", value="red"),
        as_child=False,
        value=ColorState.colors,
        disabled=False,
        required=True,
        dir="ltr",
        orientation="vertical",
        loop=True,
        on_value_change=ColorState.on_colors_change,
    )
    props = root.render()["props"]

    assert "asChild:false" in props
    assert 'dir:"ltr"' in props
    assert "disabled:false" in props
    assert "loop:true" in props
    assert 'orientation:"vertical"' in props
    assert "required:true" in props
    assert any(p.startswith("value:") for p in props)
    assert any(p.startswith("onValueChange:") for p in props)


def test_checkbox_group_item_required_renders():
    """Required must be settable per-item, matching radio_group.item."""
    item = checkbox_group.item("Red", value="red", required=True)
    assert "required:true" in item.render()["props"]


def test_checkbox_group_root_is_form_control():
    assert CheckboxGroupRoot._is_form_control is True
