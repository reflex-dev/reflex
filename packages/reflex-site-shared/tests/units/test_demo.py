"""Regression tests for shared documentation demo controls."""

from reflex_site_shared.components.blocks.demo import docdemo

import reflex as rx


def test_build_mark_uses_contrasting_theme_colors():
    """Keep the build action's mark readable in both color modes."""
    rendered = str(docdemo("rx.text('Example')", comp=rx.text("Example")))
    assert "Start Building Now!" in rendered
    assert 'className:"text-primary"' in rendered
    assert rendered.count("var(--primary-foreground)") == 2


def test_selected_demo_tab_has_a_contrasting_surface():
    """Keep the selected tab connected to the neutral demo surface."""
    from reflex_site_shared.components.blocks.tabs import doc_tab_trigger

    classes = str(doc_tab_trigger("View", value="view", icon="eye").class_name)
    assert "data-[state=active]:!bg-secondary-2" in classes
    assert "data-[state=active]:!text-secondary-12" in classes
    assert "dark:data-[state=active]:!bg-muted" not in classes
