from reflex_components_radix.themes.color_mode import ColorModeIconButton


def test_color_mode_icon_button_accessible_defaults():
    props = ColorModeIconButton.create().render()["props"]

    assert '"aria-label":"Toggle color mode"' in props
    assert 'title:"Toggle color mode"' in props


def test_color_mode_icon_button_accessible_overrides():
    props = ColorModeIconButton.create(
        aria_label="Switch theme",
        title="Switch theme",
    ).render()["props"]

    assert '"aria-label":"Switch theme"' in props
    assert 'title:"Switch theme"' in props
