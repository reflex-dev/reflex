from reflex_components_core.core.sticky import StickyBadge


def test_sticky_badge_accessible_name():
    props = StickyBadge.create().render()["props"]

    assert '"aria-label":"Built with Reflex"' in props
    assert 'title:"Built with Reflex"' in props
