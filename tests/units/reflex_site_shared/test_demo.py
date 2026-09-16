"""Regression tests for shared documentation demo controls."""

from reflex_site_shared.components.blocks.demo import _reflex_build_icon


def test_build_mark_uses_contrasting_theme_colors():
    """Keep the R visible against its tile in both color modes."""
    icon = _reflex_build_icon()
    assert str(icon.class_name) == "text-primary"
    paths = [child for child in icon.children if child.tag == "path"]
    assert len(paths) == 2
    assert all(
        str(path.fill).strip('"') == "var(--primary-foreground)" for path in paths
    )


def test_selected_demo_tab_has_a_contrasting_surface():
    """Distinguish the current panel with the primary background/text pair."""
    from reflex_site_shared.components.blocks.tabs import doc_tab_trigger

    classes = str(doc_tab_trigger("View", value="view", icon="eye").class_name)
    assert "data-[state=active]:!bg-primary" in classes
    assert "data-[state=active]:!text-primary-foreground" in classes
    assert "dark:data-[state=active]:!bg-muted" not in classes
