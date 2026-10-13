from reflex_components_radix.themes.components.checkbox_group import checkbox_group

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
    """The root renders the controlled value, its change handler, and the native props."""
    root = checkbox_group.root(
        checkbox_group.item("Red", value="red"),
        value=ColorState.colors,
        disabled=False,
        required=True,
        dir="ltr",
        orientation="vertical",
        loop=True,
        on_value_change=ColorState.on_colors_change,
    )
    props = root.render()["props"]

    assert 'dir:"ltr"' in props
    assert "disabled:false" in props
    assert "loop:true" in props
    assert 'orientation:"vertical"' in props
    assert "required:true" in props
    assert f"value:{ColorState.colors!s}" in props
    on_value_change = next(p for p in props if p.startswith("onValueChange:"))
    assert 'on_colors_change", ({ ["value"] : _ev_0 })' in on_value_change


def test_checkbox_group_item_required_renders():
    """An item renders its own required prop."""
    item = checkbox_group.item("Red", value="red", required=True)
    assert "required:true" in item.render()["props"]
