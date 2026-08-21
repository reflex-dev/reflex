from reflex_components_core.ui.theme import DARK_TOKENS, LIGHT_TOKENS, Theme


def test_default_stylesheet_contains_all_tokens() -> None:
    """The generated stylesheet defines every token in both modes."""
    css = Theme().stylesheet()

    for name, value in LIGHT_TOKENS.items():
        assert f"--{name}: {value};" in css
    for name in DARK_TOKENS:
        assert f"--{name}:" in css
    assert ":root {" in css
    assert ".dark {" in css
    assert "--radius: 0.625rem;" in css


def test_stylesheet_maps_tokens_to_tailwind_theme() -> None:
    """Every color token gets a --color-* mapping inside @theme inline."""
    css = Theme().stylesheet()

    assert "@theme inline {" in css
    for name in LIGHT_TOKENS:
        assert f"--color-{name}: var(--{name});" in css
    assert "--radius-lg: var(--radius);" in css
    assert "--radius-sm: calc(var(--radius) - 4px);" in css


def test_stylesheet_styles_body_from_tokens() -> None:
    """The body picks up the background and foreground tokens."""
    css = Theme().stylesheet()

    assert "background-color: var(--background);" in css
    assert "color: var(--foreground);" in css


def test_theme_overrides_and_custom_tokens() -> None:
    """Overrides replace defaults and custom tokens get utility mappings."""
    css = Theme(
        radius="1rem",
        light={"primary": "oklch(0.6 0.2 250)", "brand": "oklch(0.7 0.1 120)"},
        dark={"primary_foreground": "black"},
    ).stylesheet()

    assert "--radius: 1rem;" in css
    assert "--primary: oklch(0.6 0.2 250);" in css
    assert "--brand: oklch(0.7 0.1 120);" in css
    assert "--color-brand: var(--brand);" in css
    assert "--primary-foreground: black;" in css
