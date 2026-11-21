from reflex_components_radix.themes.components.avatar import Avatar


def test_alt_renders_as_an_image_prop():
    """Alternative text reaches the avatar image instead of becoming a style."""
    avatar = Avatar.create(src="/logo.png", alt="Reflex logo", fallback="RX")

    assert avatar.render()["props"] == [
        'alt:"Reflex logo"',
        'fallback:"RX"',
        'src:"/logo.png"',
    ]
