from reflex_components_core.el.elements.metadata import Link


def test_link_as_prop():
    """The link element renders the as_ prop as the HTML `as` attribute (for rel='preload')."""
    props = Link.create(
        rel="preload",
        href="/fonts/My.woff2",
        as_="font",
        type="font/woff2",
        cross_origin="anonymous",
    ).render()["props"]
    assert 'as:"font"' in props
    assert 'rel:"preload"' in props
